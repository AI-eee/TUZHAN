const fs = require('fs');
const jsdom = require("jsdom");
const { JSDOM } = jsdom;
const html = fs.readFileSync('temp2.html', 'utf8');

const virtualConsole = new jsdom.VirtualConsole();
virtualConsole.on("error", (err) => {
  console.error("JSDOM Error:", err);
});
virtualConsole.on("log", (msg) => {
  console.log("JSDOM Log:", msg);
});

const dom = new JSDOM(html, { 
    runScripts: "dangerously", 
    url: "http://localhost:8888/dashboard#tab-profile",
    virtualConsole 
});
dom.window.addEventListener('DOMContentLoaded', () => {
    console.log("Active content IDs:", Array.from(dom.window.document.querySelectorAll('.tab-content.active')).map(e => e.id));
    console.log("Active tab IDs:", Array.from(dom.window.document.querySelectorAll('.tab-btn.active')).map(e => e.textContent));
});
