import inspect
import pydoc
import signal
from typing import Any, Optional, Union

import blessed
import rich
from blessed import Terminal
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from .cached_object import CachedObject
from .explorer_layout import ExplorerLayout, ExplorerState
from .filter_layout import FilterLayout
from .help_layout import HelpLayout, HelpState, random_error_quote
from .overview_layout import OverviewLayout, OverviewState, PreviewState
from .stack_layout import StackFrame, StackLayout
from .utils import is_selectable

version = "1.3.0"

# TODO search filter


console = Console()


class Explorer:
    """ Explorer class used to interactively explore Python Objects """

    def __init__(self, obj: Any, name_of_obj: str):
        cached_obj = CachedObject(obj, attr_name=name_of_obj)
        # Figure out all the attributes of the current obj's attributes
        cached_obj.cache()

        # self.head_obj = cached_obj
        self.cached_obj: CachedObject = cached_obj
        self.term = Terminal()
        self.stack = StackLayout(head_obj=self.cached_obj, visible=False)
        self.help_layout = HelpLayout(version, visible=False, ratio=3)
        self.explorer_layout = ExplorerLayout(cached_obj=cached_obj)
        self.overview_layout = OverviewLayout(ratio=3)
        self.filter_layout = FilterLayout(visible=False)

        self.stack.append(
            StackFrame(
                cached_obj=self.cached_obj,
                explorer_layout=self.explorer_layout,
                overview_layout=self.overview_layout,
            )
        )

        # Run self.draw() whenever the win change signal is caught
        try:
            signal.signal(signal.SIGWINCH, self.draw)
        except AttributeError:
            # OS does not have SIGWINCH signal
            pass

    def explore(self) -> Optional[Any]:
        """ Open the interactive explorer """

        key = None
        res = None

        # Clear the screen
        print(self.term.clear, end="")

        with self.term.cbreak(), self.term.hidden_cursor():
            while key not in ("q", "Q"):
                try:
                    self.draw()
                    key = self.term.inkey()
                    res = self.process_key_event(key)

                    # If the object is returned as a response then close the explorer and return the selected object
                    if res:
                        break

                except RuntimeError as err:
                    # Some kind of error during resizing events. Ignore and continue
                    if (
                        err.args[0]
                        == "reentrant call inside <_io.BufferedWriter name='<stdout>'>"
                    ):
                        pass
                    # Otherwise it is a new error. Raise
                    else:
                        raise err
        return res

    def process_key_event(self, key: blessed.keyboard.Keystroke) -> Any:
        """ Process the incoming key """

        if key == "b":
            breakpoint()
            return

        # Help page ###########################################################

        if self.help_layout.visible:
            # Close help page
            if key == "?" or key.code == self.term.KEY_ESCAPE:
                self.help_layout.visible = False
                return

            # Fullscreen
            elif key == "f":
                with console.capture() as capture:
                    console.print(self.help_layout.text)
                str_out = capture.get()
                pydoc.pager(str_out)
                return

            # Switch panes
            elif key in ("{", "}", "[", "]"):
                if self.help_layout.state == HelpState.keybindings:
                    self.help_layout.state = HelpState.about
                elif self.help_layout.state == HelpState.about:
                    self.help_layout.state = HelpState.keybindings
                return

            elif key in ("j", "k", "o", "n") or key.code in (
                self.term.KEY_UP,
                self.term.KEY_DOWN,
            ):
                # Continue on and process these keys as normal
                self.help_layout.visible = False

            else:
                return

        if self.help_layout.visible is False and key == "?":
            self.help_layout.visible = True
            return

        # Navigation ##########################################################

        if key == "k" or key.code == self.term.KEY_UP:
            if self.stack.visible:
                self.stack.move_up()
            elif self.filter_layout.visible:
                self.filter_layout.move_up()
            else:
                self.explorer_layout.move_up()

        elif key == "j" or key.code == self.term.KEY_DOWN:
            if self.stack.visible:
                self.stack.move_down(self.panel_height)
            elif self.filter_layout.visible:
                self.filter_layout.move_down()
            else:
                self.explorer_layout.move_down(self.panel_height, self.cached_obj)

        elif key in ("\n", " ") and self.filter_layout.visible:
            self.filter_layout.toggle(cached_obj=self.cached_obj)

        elif key in ("\n", "l", " ") or key.code == self.term.KEY_RIGHT:

            if self.stack.visible:
                # If you are choosing the same frame as the current obj, then don't do anything
                if self.stack[self.stack.index].cached_obj == self.cached_obj:
                    return
                new_cached_obj = self.stack.select()
            else:
                new_cached_obj = self.explorer_layout.selected_object
                if not is_selectable(new_cached_obj.obj):
                    return

            self.explorer_layout = ExplorerLayout(cached_obj=new_cached_obj)
            self.cached_obj = new_cached_obj
            self.cached_obj.cache()
            self.stack.append(
                StackFrame(
                    cached_obj=self.cached_obj,
                    explorer_layout=self.explorer_layout,
                    overview_layout=self.overview_layout,
                )
            )

        # Escape
        elif (key in ("\x1b", "h") or key.code == self.term.KEY_LEFT) and self.stack:
            self.stack.pop()
            self.cached_obj = self.stack[-1].cached_obj
            self.explorer_layout = self.stack[-1].explorer_layout
            self.overview_layout = self.stack[-1].overview_layout

        elif key == "g":
            self.explorer_layout.move_top()

        elif key == "G":
            self.explorer_layout.move_bottom(self.panel_height, self.cached_obj)

        # View ################################################################

        if key == "o":
            if self.stack.visible:
                self.stack.visible = False
            elif self.filter_layout.visible:
                self.filter_layout.visible = False
                self.stack.set_visible()
            else:
                self.stack.set_visible()

        elif key == "n":
            if self.filter_layout.visible:
                self.filter_layout.visible = False
            elif self.stack.visible:
                self.stack.visible = False
                self.filter_layout.visible = True
            else:
                self.filter_layout.visible = True

        elif key == "c" and self.filter_layout.visible:
            self.filter_layout.clear_filters(self.cached_obj)

        # Switch between public and private attributes
        elif key in ("[", "]"):
            if self.explorer_layout.state == ExplorerState.public:
                self.explorer_layout.state = ExplorerState.private

            elif self.explorer_layout.state == ExplorerState.private:
                self.explorer_layout.state = ExplorerState.public

        elif key in ("{", "}"):
            if not callable(self.explorer_layout.selected_object.obj):
                return

            if self.overview_layout.preview_state == PreviewState.repr:
                self.overview_layout.preview_state = PreviewState.source
            elif self.overview_layout.preview_state == PreviewState.source:
                self.overview_layout.preview_state = PreviewState.repr

        # Toggle docstring view
        elif key == "d":
            self.overview_layout.state = (
                OverviewState.docstring
                if self.overview_layout.state != OverviewState.docstring
                else OverviewState.all
            )

        # Toggle value view
        elif key == "p":
            self.overview_layout.state = (
                OverviewState.value
                if self.overview_layout.state != OverviewState.value
                else OverviewState.all
            )

        # Fullscreen
        elif key == "f":
            printable: Union[str, Syntax]

            if self.overview_layout.state == OverviewState.docstring:
                printable = self.explorer_layout.selected_object.docstring

            elif self.overview_layout.preview_state == PreviewState.repr:
                printable = self.explorer_layout.selected_object.obj

            elif self.overview_layout.preview_state == PreviewState.source:
                printable = self.explorer_layout.selected_object.get_source(
                    fullscreen=True
                )

            with console.capture() as capture:
                console.print(printable)

            str_out = capture.get()
            pydoc.pager(str_out)

        elif key == "H":
            help(self.explorer_layout.selected_object())

        elif key == "i":
            with console.capture() as capture:
                rich.inspect(
                    self.explorer_layout.selected_object.obj,
                    console=console,
                    methods=True,
                )
            str_out = capture.get()
            pydoc.pager(str_out)

        elif key == "I":
            with console.capture() as capture:
                rich.inspect(
                    self.explorer_layout.selected_object.obj, console=console, all=True
                )
            str_out = capture.get()
            pydoc.pager(str_out)

        # Other ################################################################

        # Return selected object
        elif key == "r":
            return self.explorer_layout.selected_object.obj

    def get_explorer_layout(self) -> Layout:
        if self.stack.visible:
            layout = Layout()
            layout.split_column(
                self.explorer_layout(
                    term_width=self.term.width, term_height=self.term.height,
                ),
                self.stack(term_width=self.term.width),
            )
            return layout
        elif self.filter_layout.visible:
            layout = Layout()
            layout.split_column(
                self.explorer_layout(
                    term_width=self.term.width, term_height=self.term.height,
                ),
                self.filter_layout()
            )
            return layout
        else:
            return self.explorer_layout(
                term_width=self.term.width, term_height=self.term.height,
            )

    def get_overview_layout(self) -> Layout:
        if self.help_layout.visible:
            return self.help_layout()
        else:
            return self.overview_layout(
                cached_obj=self.explorer_layout.selected_object,
                term_height=self.term.height,
                console=console,
            )

    def draw(self, *args):
        """ Draw the application. the *args argument is due to resize events and are unused """
        print(self.term.home, end="")
        layout = Layout()

        layout.split_row(self.get_explorer_layout(), self.get_overview_layout())

        title = self.cached_obj.dotpath + Text(" | ", style="white") + self.cached_obj.typeof

        object_explorer = Panel(
            layout,
            title=title,
            subtitle=(
                "[red][u]q[/u]:quit[/red] "
                f"[cyan][u]?[/u]:{'exit ' if self.help_layout.visible else ''}help[/] "
                "[white][dim][u]o[/u]:stack [u]n[/u]:filter [u]r[/u]:return[/dim]"
            ),
            subtitle_align="left",
            height=self.term.height - 1,
            style="blue",
        )
        rich.print(object_explorer, end="")

    @property
    def panel_height(self) -> int:
        # TODO this shouldn't be here
        if self.stack.visible:
            return (self.term.height - 10) // 2
        else:
            return self.term.height - 6


def explore(obj: Any) -> Any:
    """ Run the explorer on the given object """
    try:
        frame = inspect.currentframe()
        name = frame.f_back.f_code.co_names[1]
        e = Explorer(obj, name_of_obj=name)
        return e.explore()
    except Exception as err:
        console.print_exception(show_locals=True)
        print()
        rich.print(f"[red]{random_error_quote()}")
        formatted_link = f"https://github.com/kylepollina/objexplore/issues/new?assignees=&labels=&template=bug_report.md&title={err}".replace(
            " ", "+"
        )
        print("Please report the issue here:")
        rich.print(f"   [link={formatted_link}][u]{formatted_link}[/u][/link]")
        print()
        rich.print(
            "[yellow italic]Make sure to copy/paste the above traceback to the issue page to make this quicker to fix :)"
        )
