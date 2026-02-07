#include <ass/ass.h>
#include <iostream>

int main() {
  ASS_Library* lib = ass_library_init();
  std::cout << (lib ? "libass OK\n" : "libass FAIL\n");
  if (lib) ass_library_done(lib);
  return lib ? 0 : 1;
}
