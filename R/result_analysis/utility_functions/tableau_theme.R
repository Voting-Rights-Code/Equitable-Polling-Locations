# Tableau-style ggplot2 theme and color scales

# Colorblind-safe 10-color categorical palette.
# First 8 colors are the Okabe-Ito palette (Wong 2011, Nature Methods),
# validated to be distinguishable under deuteranopia, protanopia, and
# tritanopia.  Positions 9-10 extend with indigo and teal from Paul Tol's
# muted palette.
#

TABLEAU_COLORS <- c(
    "#332288",  # [9]  indigo        (Paul Tol muted)
    "#E69F00",  # [2]  orange        (Okabe-Ito)
    "#D55E00",  # [3]  vermillion    (Okabe-Ito)
    "#009E73",  # [4]  bluish green  (Okabe-Ito)
    "#CC79A7",  # [5]  reddish purple(Okabe-Ito)
    "#0072B2",  # [1]  blue          (Okabe-Ito)
    "#F0E442",  # [6]  yellow        (Okabe-Ito)
    "#56B4E9",  # [7]  sky blue      (Okabe-Ito)
    "#999999",  # [8]  gray
    "#44AA99"   # [10] teal          (Paul Tol muted)
)

# Wraps long plot titles/subtitles onto multiple lines instead of letting
# them run off the edge of the saved image (element_text has no wrapping
# of its own, and ggtext::element_textbox isn't a project dependency).
element_textwrap <- function(width = 50, ...) {
    et <- element_text(...)
    attr(et, "wrap_width") <- width
    class(et) <- c("element_textwrap", class(et))
    et
}

element_grob.element_textwrap <- function(element, label = "", ...) {
    width <- attr(element, "wrap_width")
    if (!is.null(label) && nzchar(label) && !is.null(width)) {
        label <- paste(strwrap(label, width = width), collapse = "\n")
    }
    NextMethod()
}

theme_tableau <- function(base_size = 11, base_family = "sans",
                           title_wrap_width = 50, subtitle_wrap_width = 50) {
    theme_bw(base_size = base_size, base_family = base_family) %+replace%
        theme(
            # Background
            plot.background   = element_rect(fill = "white", color = NA),
            panel.background  = element_rect(fill = "white", color = NA),

            # Grid: horizontal light gray only (Tableau default)
            panel.grid.major.x = element_blank(),
            panel.grid.minor.x = element_blank(),
            panel.grid.major.y = element_line(color = "#E0E0E0", linewidth = 0.4),
            panel.grid.minor.y = element_blank(),

            # Axis lines: thin dark line on x, none on y
            axis.line.x  = element_line(color = "#333333", linewidth = 0.4),
            axis.line.y  = element_blank(),
            axis.ticks.x = element_line(color = "#333333", linewidth = 0.4),
            axis.ticks.y = element_blank(),

            # Panel border: none
            panel.border = element_blank(),

            # Title and labels
            plot.title    = element_textwrap(width = title_wrap_width,
                                         face = "bold", size = base_size + 1,
                                         color = "#333333", hjust = 0,
                                         margin = margin(b = 6)),
            plot.subtitle = element_textwrap(width = subtitle_wrap_width,
                                         size = base_size, color = "#666666",
                                         hjust = 0, margin = margin(b = 8)),
            axis.title    = element_text(size = base_size, color = "#333333"),
            axis.text     = element_text(size = base_size - 1, color = "#555555"),
            axis.text.x   = element_text(angle = 90, hjust = 1, vjust = 0.5),

            # Legend
            legend.background = element_rect(fill = "white", color = NA),
            legend.key        = element_rect(fill = "white", color = NA),
            legend.title      = element_text(face = "bold", size = base_size - 1,
                                             color = "#333333"),
            legend.text       = element_text(size = base_size - 1, color = "#555555"),
            legend.position   = "right",

            # Strip (facet labels)
            strip.background = element_rect(fill = "#F5F5F5", color = "#CCCCCC",
                                            linewidth = 0.4),
            strip.text       = element_text(face = "bold", size = base_size - 1,
                                            color = "#333333"),

            # Caption: left-aligned to full plot width to prevent clipping
            plot.caption          = element_text(size = base_size - 2,
                                                 color = "#666666", hjust = 0,
                                                 margin = margin(t = 6)),
            plot.caption.position = "plot",

            # Margins
            plot.margin = margin(12, 16, 12, 12)
        )
}

scale_color_tableau <- function(...) {
    scale_color_manual(values = TABLEAU_COLORS, ...)
}

scale_fill_tableau <- function(...) {
    scale_fill_manual(values = TABLEAU_COLORS, ...)
}

# Colorblind-safe sequential gradient for map distance choropleth/dots.
# Uses ColorBrewer YlOrRd: light yellow → dark red.
# Single-hue warm scale ensures overlay point colors (cool blues/teal)
# are always visually distinct, even under deuteranopia/protanopia.
scale_fill_map_distance <- function(...) {
    scale_fill_gradient(low = "#FFFFB2", high = "#BD0026", ...)
}

scale_color_map_distance <- function(...) {
    scale_color_gradient(low = "#FFFFB2", high = "#BD0026", ...)
}

# Colorblind-safe discrete colors for poll-type points overlaid on maps.
# Drawn from the Okabe-Ito palette, designed to be distinguishable under
# deuteranopia, protanopia, and tritanopia, and to contrast with the
# warm YlOrRd gradient background.
#   polling     – Okabe-Ito blue       (#0072B2)
#   potential   – Okabe-Ito blue-green (#009E73)
#   bg_centroid – neutral gray         (#BBBBBB, de-emphasized)
MAP_POLL_TYPE_COLORS <- c(
    polling     = "#0072B2",
    potential   = "#009E73",
    bg_centroid = "#BBBBBB"
)

MAP_POLL_TYPE_SHAPES <- c(
    polling     = 16,
    potential   = 17,
    bg_centroid = 15
)

# Map variant: suppress all axis/grid elements for clean geographic rendering
theme_tableau_map <- function(base_size = 11, base_family = "sans",
                               title_wrap_width = 50, subtitle_wrap_width = 50) {
    theme_tableau(base_size = base_size, base_family = base_family,
                  title_wrap_width = title_wrap_width,
                  subtitle_wrap_width = subtitle_wrap_width) %+replace%
        theme(
            axis.text.x  = element_blank(),
            axis.text.y  = element_blank(),
            axis.ticks   = element_blank(),
            axis.line.x  = element_blank(),
            panel.grid.major.y = element_blank(),
            panel.background = element_rect(fill = "#F7F7F7", color = NA)
        )
}
