/* src/static/js/ui.js */

window.TZUI = {
    setup() {
        if (!document.getElementById('tz-toast-container')) {
            const c = document.createElement('div');
            c.id = 'tz-toast-container';
            c.className = 'tz-toast-container';
            document.body.appendChild(c);
        }
        if (!document.getElementById('tz-confirm-overlay')) {
            const m = document.createElement('div');
            m.id = 'tz-confirm-overlay';
            m.className = 'tz-confirm-overlay';
            m.innerHTML = `
                <div class="tz-confirm-box" onclick="event.stopPropagation()">
                    <div class="tz-confirm-msg" id="tz-confirm-msg"></div>
                    <div class="tz-confirm-actions">
                        <button class="tz-btn tz-btn-cancel" id="tz-confirm-cancel">取消</button>
                        <button class="tz-btn tz-btn-ok" id="tz-confirm-ok">确定</button>
                    </div>
                </div>
            `;
            // 点击外部遮罩不关闭，保持类似原生的行为
            document.body.appendChild(m);
        }
    },
    
    toast(msg, type = 'info', duration = 3000) {
        this.setup();
        const container = document.getElementById('tz-toast-container');
        const t = document.createElement('div');
        t.className = `tz-toast ${type}`;
        t.innerText = msg;
        container.appendChild(t);
        
        setTimeout(() => {
            t.style.animation = 'toastOut 0.3s ease forwards';
            t.addEventListener('animationend', () => t.remove());
        }, duration);
    },
    
    confirm(msg, onConfirm) {
        this.setup();
        const overlay = document.getElementById('tz-confirm-overlay');
        const msgEl = document.getElementById('tz-confirm-msg');
        const cancelBtn = document.getElementById('tz-confirm-cancel');
        const okBtn = document.getElementById('tz-confirm-ok');
        
        msgEl.innerText = msg;
        overlay.style.display = 'flex';
        
        // 绑定清理函数
        const cleanup = () => {
            overlay.style.display = 'none';
            cancelBtn.onclick = null;
            okBtn.onclick = null;
        };
        
        cancelBtn.onclick = () => { cleanup(); };
        okBtn.onclick = () => { cleanup(); onConfirm(); };
    }
};