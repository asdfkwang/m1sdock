list(REMOVE_ITEM GLOBAL_LD_FLAGS --specs=nano.specs)

set(TARGET_REQUIRED_SRCS rv32i_xtheade_lz4.S)
set(mains main.c)
if(${CPU_ID} STREQUAL "d0" )
    set(LINKER_SCRIPT ${CMAKE_CURRENT_SOURCE_DIR}/bl808_flash_d0.ld)
endif()
option(LOW_LOAD_RUST_D0 "Link the D0 Rust probe" OFF)
if(LOW_LOAD_RUST_D0)
    if(NOT CPU_ID STREQUAL "d0")
        message(FATAL_ERROR "LOW_LOAD_RUST_D0 requires CPU_ID=d0")
    endif()
    get_filename_component(FIRMWARE_DIR "${CMAKE_SOURCE_DIR}/../../firmware" ABSOLUTE)
    find_program(CARGO_EXECUTABLE cargo REQUIRED)
    find_program(RUST_OBJCOPY riscv64-linux-gnu-objcopy REQUIRED)
    set(RUST_TARGET_DIR "${FIRMWARE_DIR}/target")
    set(RUST_LIBRARY "${RUST_TARGET_DIR}/riscv64gc-unknown-none-elf/release/libm1s_d0.a")
    add_custom_target(d0_rust_build
        COMMAND "${CARGO_EXECUTABLE}" build --release --locked --offline
            --target riscv64gc-unknown-none-elf --target-dir "${RUST_TARGET_DIR}"
        WORKING_DIRECTORY "${FIRMWARE_DIR}"
        BYPRODUCTS "${RUST_LIBRARY}"
        VERBATIM)
    # Old vendor binutils cannot parse modern ISA attribute names.
    # Drop only attributes on a link-only copy; preserve code and ABI flags.
    set(RUST_LINK_LIBRARY "${CMAKE_BINARY_DIR}/libm1s_d0_vendor.a")
    add_custom_target(d0_rust_vendor_archive
        COMMAND "${RUST_OBJCOPY}" --remove-section=.riscv.attributes
            "${RUST_LIBRARY}" "${RUST_LINK_LIBRARY}"
        BYPRODUCTS "${RUST_LINK_LIBRARY}"
        VERBATIM)
    add_dependencies(d0_rust_vendor_archive d0_rust_build)
    add_library(d0_rust STATIC IMPORTED)
    set_target_properties(d0_rust PROPERTIES IMPORTED_LOCATION "${RUST_LINK_LIBRARY}")
    add_dependencies(d0_rust d0_rust_vendor_archive)
    list(APPEND GLOBAL_C_FLAGS -DLOW_LOAD_RUST_D0)
    set(OUTPUT "${CMAKE_BINARY_DIR}/out")
endif()

generate_bin()

if(LOW_LOAD_RUST_D0)
    target_link_libraries(firmware.elf d0_rust)
endif()
