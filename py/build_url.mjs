#!/usr/bin/env node
// 4kvms.org WASM play URL builder
// Usage: node build_url.mjs <dataid> <secretKey> <quality> <playKey>
// Output: JSON with the play URL

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
    const args = process.argv.slice(2);
    if (args.length < 4) {
        console.error(JSON.stringify({error: "Usage: node build_url.mjs <dataid> <secretKey> <quality> <playKey>"}));
        process.exit(1);
    }

    const [dataid, secretKey, quality, playKey] = args;

    try {
        // Look for WASM files in the same directory as this script
        const wasmPath = path.join(__dirname, 'nbmovie_wasm_bg.d5d51939.wasm');
        const wasmJsPath = path.join(__dirname, 'nbmovie_wasm.426511b7.js');

        if (!fs.existsSync(wasmPath)) {
            throw new Error('WASM file not found: ' + wasmPath);
        }
        if (!fs.existsSync(wasmJsPath)) {
            throw new Error('WASM JS glue not found: ' + wasmJsPath);
        }

        // Read the JS glue code
        let jsCode = fs.readFileSync(wasmJsPath, 'utf8');

        // Remove export keywords and import.meta references
        jsCode = jsCode.replace(/export function/g, 'function');
        jsCode = jsCode.replace(/export \{[^}]*\};?/g, '');
        // Replace import.meta.url with a dummy value - we'll pass wasm path directly
        jsCode = jsCode.replace(/new URL\('nbmovie_wasm_bg\.wasm', import\.meta\.url\)/g, "''");

        // Build full code with init and call
        const fullCode = `
            ${jsCode}

            async function init() {
                const wasmBuffer = fs.readFileSync('${wasmPath}');
                const wasmModule = await WebAssembly.compile(wasmBuffer);
                const imports = __wbg_get_imports();
                const instance = await WebAssembly.instantiate(wasmModule, imports);
                __wbg_finalize_init(instance, wasmModule);
            }

            await init();
            const url = build_play_url('${dataid}', '${secretKey}', '${quality}', '${playKey}');
            console.log(JSON.stringify({url: url}));
        `;

        // Use async function wrapper
        const asyncFn = new Function('fs', 'return (async () => { ' + fullCode + ' })();');
        await asyncFn(fs);
    } catch(e) {
        console.error(JSON.stringify({error: e.message, stack: e.stack}));
        process.exit(1);
    }
}

main();