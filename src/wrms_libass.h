#pragma once
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void* wrms_handle_t;

// Un "sprite" de libass (A8 + color + posición)
typedef struct {
  int x;
  int y;
  int w;
  int h;
  int stride;      // bytes por fila en bitmap
  uint32_t color;  // formato libass (ver docs/ass.h) - tú lo interpretas en Python
  uint32_t offset; // offset dentro de `bitmaps` donde empieza este bitmap A8
} wrms_sprite_t;

// Un frame renderizado: lista de sprites + un blob con todos los bitmaps A8 concatenados
typedef struct {
  wrms_sprite_t* sprites;
  size_t sprites_len;

  uint8_t* bitmaps;
  size_t bitmaps_len;
} wrms_frame_t;

// lifecycle
wrms_handle_t wrms_create();
void wrms_destroy(wrms_handle_t h);

// Track
// returns 0 ok, !=0 error
int wrms_set_track(wrms_handle_t h, const char* ass_utf8, size_t ass_len);

// Renderer params (para que libass calcule cosas a ese size)
int wrms_set_frame_size(wrms_handle_t h, int width, int height);

// Render A8 sprites for t_ms
// returns 0 ok, !=0 error. Si no hay subs en ese tiempo: frame->sprites_len = 0 y bitmaps_len=0
int wrms_render_a8(wrms_handle_t h, int t_ms, wrms_frame_t* out_frame);

// Liberar buffers devueltos por wrms_render_a8
void wrms_free_frame(wrms_frame_t* frame);

#ifdef __cplusplus
}
#endif
