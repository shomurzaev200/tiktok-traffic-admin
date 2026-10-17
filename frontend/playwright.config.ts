import {defineConfig} from '@playwright/test';
export default defineConfig({testMatch:'e2e.spec.ts',workers:1,use:{headless:true},reporter:'list',timeout:60000});
