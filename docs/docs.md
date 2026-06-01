# Local Documentation

This document explains how to build and view the MeshCore documentation locally.

## Building and viewing Docs

```
pip install mkdocs
pip install mkdocs-material
```

- `mkdocs serve` - Start the live-reloading docs server.
- `mkdocs build` - Build the documentation site.

## Building and viewing the MeshCoreNG website

The MeshCoreNG GitHub Pages site is kept in `website/` and includes the public web flasher.

```
cd website
npm install
npm run dev
```

- `npm run dev` - Start the local VitePress docs site.
- `npm run build` - Build the static GitHub Pages site.

The static flasher lives in `website/public/flasher/`. It is copied into the published site as `/flasher/`.
