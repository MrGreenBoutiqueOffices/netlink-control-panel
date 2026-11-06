#pragma once
#include <stdint.h>
#include <stddef.h>
struct DemoGlyph { uint32_t offset; uint16_t width,height; int16_t x,y,advance; };
struct DemoFont { const uint8_t *pixels; const DemoGlyph *glyphs; int size; };
extern const uint16_t *const demoFrames[25];
extern const uint32_t demoFrameWords[25];
extern const DemoFont demoFonts[11];
