# Documentation

The book uses mdBook 0.4.36. Its third chapter embeds a React Flow application,
built locally with Vite. Node.js 24 or newer is required for the frontend build
and the native TypeScript tests.

```sh
cargo install mdbook --version 0.4.36
cd docs
npm ci
npm test
npm run build
npm run serve -- --hostname 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/boot-sequence.html`. `npm run build` runs the
TypeScript check, builds React / React Flow into `theme/boot-sequence/`, then
builds mdBook. The generated bundles and book output are not committed;
GitHub Pages runs the same frontend build before mdBook.

For frontend development, `npm run dev` opens a standalone Vite preview.
To rebuild into an already-running mdBook preview, use `npm run watch:boot`
in a second terminal. The chapter inherits the book's theme and the memory
map's BL808 color tokens. No CDN or runtime Node.js service is required.

Only the M0 runtime and D0 synchronization scenes are playable. The chapter's
storyboard documents the remaining flow. The dedicated Flash-kernel stage
is a storage plan; this animation does not implement firmware or flash it.
