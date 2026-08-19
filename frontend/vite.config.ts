import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig} from 'vite';

// 部署時整包掛在 https://taiwansilver.shop/539/ 底下,所以 base 要帶 /539/。
// 開發時 vite 跑 3000 埠,/api 轉給本機 FastAPI(8540)。
// BASE_PATH 可覆寫(正式 /539/、並排預覽 /539n/)。client.ts 用 import.meta.env.BASE_URL
// 讀這個值組 API 網址,所以前後端只要 build 時帶對 BASE_PATH 就一致。
const BASE_PATH = process.env.BASE_PATH || '/539/';

export default defineConfig(() => {
  return {
    base: BASE_PATH,
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      port: 3000,
      host: '0.0.0.0',
      proxy: {
        // 後端 dev 也帶 APP_PREFIX=/539,路由是 /539/api/*,與正式環境一致
        '/539/api': {
          target: 'http://127.0.0.1:8540',
          changeOrigin: true,
        },
      },
    },
  };
});
