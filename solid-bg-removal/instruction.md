# Remove Solid-Color Backgrounds

The directory `/app/input/` contains several `.png` photos. Each photo shows one
or more foreground objects placed over a **single solid background color** (a
studio-style backdrop). The background color may differ from photo to photo, but
within a given photo the background is one uniform color (you can sample it from
the image corners, which are always background).

Write a program that removes the background from every photo and saves the result
as a transparent PNG.

## Requirements

- Process **every** `.png` file in `/app/input/`.
- For each input, write an output PNG to `/app/output/` using the **same
  filename** (e.g. `/app/input/studio_white.png` -> `/app/output/studio_white.png`).
  Create `/app/output/` if it does not exist.
- Each output must be **RGBA**: background pixels fully transparent
  (alpha `0`) and foreground pixels fully opaque (alpha `255`). Anti-aliased edge
  pixels may take intermediate alpha values.
- The output image must have the **same width and height** as its input.

Your program should be general (infer the background color per image rather than
hard-coding it). After it runs, `/app/output/` should contain one transparent PNG
per input photo.
