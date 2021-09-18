
from typing import Optional

from rich.layout import Layout
from rich.style import Style
from rich.panel import Panel
from rich.pretty import Pretty
from rich.text import Text

from .cached_object import CachedObject
from .utils import is_selectable


class OverviewState:
    all, docstring, value = range(3)


class PreviewState:
    repr, source = range(2)


class OverviewLayout(Layout):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state = OverviewState.all
        self.preview_state = PreviewState.repr

    def __call__(self, cached_obj: CachedObject, term_height: int, console) -> Layout:
        """
        :param cached_obj: The selected cached object given by the explorer layout
        """
        if self.state == OverviewState.docstring:
            self.update(
                self.get_docstring_panel(
                    cached_obj=cached_obj,
                    term_height=term_height,
                    fullscreen=True,
                )
            )
            return self

        elif self.state == OverviewState.value:
            self.update(self.get_value_panel(cached_obj, term_height))
            return self

        else:
            layout = Layout(ratio=3)
            layout.split_column(
                Layout(self.get_value_panel(cached_obj, term_height), name="obj_value"),
                self.get_info_layout(cached_obj),
                Layout(
                    self.get_docstring_panel(cached_obj=cached_obj),
                    name="obj_doc",
                ),
            )
            return layout

    def get_value_panel(self, cached_obj: CachedObject, term_height: int):
        if is_selectable(cached_obj):
            title = "[i]preview[/i] | [i][cyan]repr[/cyan]()[/i]"
            subtitle = "[dim][u]p[/u]:toggle [u]f[/u]:fullscreen [u]{}[/u]:switch pane"
            renderable = cached_obj.pretty

            if self.state == OverviewState.all:
                renderable.max_length = (max((term_height - 6) // 2 - 7, 1))
            else:
                renderable.max_length = (max(term_height - 9, 1))

            return Panel(
                renderable,
                title=title,
                title_align="left",
                subtitle=subtitle,
                subtitle_align="left",
                style=Style(color="white")
            )

        else:
            title = "[i]preview[/i] | [i][cyan]repr[/cyan]()[/i] [dim]source"
            subtitle = "[dim][u]p[/u]:toggle [u]f[/u]:fullscreen [u]{}[/u]:switch pane"
            renderable = cached_obj.pretty

            if self.state == OverviewState.all:
                renderable.max_length = (max((term_height - 6) // 2 - 7, 1))
            else:
                renderable.max_length = (max(term_height - 9, 1))


        #     if self.state == OverviewState.all:
        #         renderable = Pretty(
        #             renderable, max_length=(max((term_height - 6) // 2 - 7, 1))
        #         )
        #     else:
        #         renderable = Pretty(renderable, max_length=(max(term_height - 9, 1)))

        # return Panel(
        #     renderable,
        #     title=title,
        #     title_align="left",
        #     subtitle=subtitle,
        #     subtitle_align="left",
        #     style="white",
        # )

    def get_info_layout(self, cached_obj: CachedObject):
        if cached_obj.length:
            layout = Layout(size=3)
            layout.split_row(
                Layout(self.get_type_panel(cached_obj)),
                Layout(
                    Panel(
                        cached_obj.length,
                        title="[i][cyan]len[/cyan]()[/i]",
                        title_align="left",
                        style="white",
                    )
                ),
            )
            return layout

        else:
            return self.get_type_panel(cached_obj)

    def get_type_panel(self, cached_obj: CachedObject):
        return Layout(
            Panel(
                cached_obj.typeof,
                title="[i][cyan]type[/cyan]()[/i]",
                title_align="left",
                style="white",
            ),
            size=3,
        )

    def get_docstring_panel(
        self,
        cached_obj: CachedObject,
        term_height: Optional[int] = None,
        fullscreen: bool = False,
    ) -> Panel:
        """ Build the docstring panel """
        title = "[i]docstring"
        docstring = Text("\n").join(cached_obj.docstring.split("\n")[:term_height])
        if fullscreen:
            return Panel(
                docstring,
                title=title,
                title_align="left",
                subtitle="[dim][u]d[/u]:toggle [u]f[/u]:fullscreen",
                subtitle_align="left",
                style="white",
            )
        else:
            # Only need to show the lines of the docstring that would be visible by
            # the terminal
            return Panel(
                docstring,
                title=title,
                title_align="left",
                subtitle="[dim][u]d[/u]:toggle",
                subtitle_align="left",
                style="white",
            )
