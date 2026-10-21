idf_component_register(
    SRCS "main.c" "ecg_frame.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES driver esp_adc esp_timer
)
