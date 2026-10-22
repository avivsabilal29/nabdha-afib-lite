idf_component_register(
    SRCS "main.c" "seg.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES driver esp_timer
)
