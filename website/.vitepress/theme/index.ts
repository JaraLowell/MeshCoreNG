import DefaultTheme from 'vitepress/theme'
import CliAppReleases from '../components/CliAppReleases.vue'
import type { Theme } from 'vitepress'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('CliAppReleases', CliAppReleases)
  },
} satisfies Theme
