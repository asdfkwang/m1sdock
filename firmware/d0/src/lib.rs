#![no_std]

use core::ffi::c_char;
use core::panic::PanicInfo;

/// Print through the initialized vendor UART and return to the C loader.
#[no_mangle]
pub extern "C" fn d0_rust_probe(print: extern "C" fn(*const c_char)) {
    print(b"D0 Rust OK\r\n\0".as_ptr().cast());
}

#[panic_handler]
fn panic(_: &PanicInfo<'_>) -> ! {
    loop {
        core::hint::spin_loop();
    }
}
