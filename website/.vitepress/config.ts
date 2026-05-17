import { defineConfig } from 'vitepress'

export default defineConfig({
  title: 'MeshCoreNG',
  description: 'Next-generation LoRa mesh firmware — smarter repeaters for denser networks',
  base: '/MeshCoreNG/',

  // /flasher/ is a static HTML page in public/ — not a VitePress page.
  ignoreDeadLinks: [/\/flasher\//],

  head: [
    ['link', { rel: 'icon', href: '/MeshCoreNG/favicon.svg' }],
  ],

  themeConfig: {
    logo: '/logo.svg',

    nav: [
      { text: 'Docs',     link: '/docs/' },
      { text: 'Flash',    link: '/flasher/', target: '_self' },
      { text: 'GitHub',   link: 'https://github.com/MichTronics/MeshCoreNG' },
      { text: 'Releases', link: 'https://github.com/MichTronics/MeshCoreNG/releases' },
    ],

    sidebar: {
      '/docs/': [
        {
          text: 'MeshCoreNG',
          items: [
            { text: 'Introduction',    link: '/docs/' },
            { text: 'Getting started', link: '/docs/getting-started' },
            { text: 'Dense mesh',      link: '/docs/dense-mesh' },
            { text: 'Internet bridge', link: '/docs/bridge' },
            { text: 'Power saving',    link: '/docs/power-saving' },
            { text: 'CLI reference',   link: '/docs/cli' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/MichTronics/MeshCoreNG' },
    ],

    footer: {
      message: 'Released under the MIT License.',
      copyright: 'MeshCoreNG – MichTronics',
    },

    search: { provider: 'local' },
  },
})
