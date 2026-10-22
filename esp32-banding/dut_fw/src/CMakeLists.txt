idf_component_register(
    SRCS "main.c" "afib_chain.c" "afib_run.c"
    INCLUDE_DIRS "."
    PRIV_REQUIRES driver esp_timer esp_pm mbedtls
    EMBED_FILES "../data/stimulus.bin"
)
# rantai dikompilasi -O2 apa pun setelan proyeknya, supaya angka siklus tidak bergantung menu
set_source_files_properties("afib_chain.c" "afib_run.c" PROPERTIES COMPILE_OPTIONS "-O2")
