import astro from "eslint-plugin-astro";

const config = [
  { ignores: ["dist/**", ".astro/**", "node_modules/**"] },
  ...astro.configs.recommended,
];

export default config;
