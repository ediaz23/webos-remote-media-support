#include "wrms_libass.h"

#include <ass/ass.h>
#include <mutex>
#include <vector>
#include <cstring>
#include <cstdlib>

struct Engine {
  ASS_Library* lib = nullptr;
  ASS_Renderer* renderer = nullptr;
  ASS_Track* track = nullptr;
  int w = 0, h = 0;
  std::mutex mtx;
};

static void free_track_locked(Engine* e) {
  if (e->track) {
    ass_free_track(e->track);
    e->track = nullptr;
  }
}

wrms_handle_t wrms_create() {
  Engine* e = new Engine();

  e->lib = ass_library_init();
  if (!e->lib) { delete e; return nullptr; }

  e->renderer = ass_renderer_init(e->lib);
  if (!e->renderer) {
    ass_library_done(e->lib);
    delete e;
    return nullptr;
  }

  // TODO (opcional): configurar fonts aquí cuando quieras:
  // ass_set_fonts(e->renderer, nullptr, "Arial", 1, nullptr, 1);

  return (wrms_handle_t)e;
}

void wrms_destroy(wrms_handle_t h) {
  if (!h) return;
  Engine* e = (Engine*)h;
  std::lock_guard<std::mutex> lk(e->mtx);

  free_track_locked(e);

  if (e->renderer) { ass_renderer_done(e->renderer); e->renderer = nullptr; }
  if (e->lib) { ass_library_done(e->lib); e->lib = nullptr; }

  delete e;
}

int wrms_set_frame_size(wrms_handle_t h, int width, int height) {
  if (!h) return 1;
  if (width <= 0 || height <= 0) return 2;

  Engine* e = (Engine*)h;
  std::lock_guard<std::mutex> lk(e->mtx);

  e->w = width;
  e->h = height;
  ass_set_frame_size(e->renderer, e->w, e->h);
  return 0;
}

int wrms_set_track(wrms_handle_t h, const char* ass_utf8, size_t ass_len) {
  if (!h) return 1;
  if (!ass_utf8 || ass_len == 0) return 2;

  Engine* e = (Engine*)h;
  std::lock_guard<std::mutex> lk(e->mtx);

  free_track_locked(e);

  // libass no necesita null-terminator si pasas len
  e->track = ass_read_memory(e->lib, (char*)ass_utf8, (int)ass_len, nullptr);
  if (!e->track) return 3;

  return 0;
}

static void frame_zero(wrms_frame_t* f) {
  if (!f) return;
  f->sprites = nullptr;
  f->sprites_len = 0;
  f->bitmaps = nullptr;
  f->bitmaps_len = 0;
}

int wrms_render_a8(wrms_handle_t h, int t_ms, wrms_frame_t* out_frame) {
  if (!h) return 1;
  if (!out_frame) return 2;
  if (t_ms < 0) return 3;

  frame_zero(out_frame);

  Engine* e = (Engine*)h;
  std::lock_guard<std::mutex> lk(e->mtx);

  if (!e->track) return 4;

  int changed = 0;
  ASS_Image* img = ass_render_frame(e->renderer, e->track, t_ms, &changed);

  if (!img) {
    // ok: no subs
    return 0;
  }

  // 1) contar sprites y bytes totales de bitmaps
  size_t n = 0;
  size_t total_bytes = 0;
  for (ASS_Image* it = img; it; it = it->next) {
    // bitmap A8: stride * h bytes
    if (it->w <= 0 || it->h <= 0 || it->stride <= 0 || !it->bitmap) continue;
    n++;
    total_bytes += (size_t)it->stride * (size_t)it->h;
  }

  if (n == 0 || total_bytes == 0) {
    return 0;
  }

  // 2) asignar
  wrms_sprite_t* sprites = (wrms_sprite_t*)std::malloc(n * sizeof(wrms_sprite_t));
  uint8_t* bitmaps = (uint8_t*)std::malloc(total_bytes);
  if (!sprites || !bitmaps) {
    if (sprites) std::free(sprites);
    if (bitmaps) std::free(bitmaps);
    return 5;
  }

  // 3) copiar
  size_t i = 0;
  size_t off = 0;
  for (ASS_Image* it = img; it; it = it->next) {
    if (it->w <= 0 || it->h <= 0 || it->stride <= 0 || !it->bitmap) continue;

    const size_t bytes = (size_t)it->stride * (size_t)it->h;

    sprites[i].x = it->dst_x;
    sprites[i].y = it->dst_y;
    sprites[i].w = it->w;
    sprites[i].h = it->h;
    sprites[i].stride = it->stride;
    sprites[i].color = (uint32_t)it->color;
    sprites[i].offset = (uint32_t)off;

    std::memcpy(bitmaps + off, it->bitmap, bytes);
    off += bytes;
    i++;
  }

  out_frame->sprites = sprites;
  out_frame->sprites_len = i;
  out_frame->bitmaps = bitmaps;
  out_frame->bitmaps_len = off;

  return 0;
}

void wrms_free_frame(wrms_frame_t* frame) {
  if (!frame) return;
  if (frame->sprites) std::free(frame->sprites);
  if (frame->bitmaps) std::free(frame->bitmaps);
  frame_zero(frame);
}
