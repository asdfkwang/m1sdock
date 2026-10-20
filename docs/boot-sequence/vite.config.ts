import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  base: './',
  define: { 'process.env.NODE_ENV': JSON.stringify('production') },
  build: {
    outDir: fileURLToPath(new URL('../theme/boot-sequence', import.meta.url)),
    emptyOutDir: true,
    lib: {
      entry: fileURLToPath(new URL('./main.tsx', import.meta.url)),
      name: 'BL808BootSequence',
      formats: ['iife'],
      fileName: () => 'boot-sequence.js',
      cssFileName: 'boot-sequence',
    },
  },
});
