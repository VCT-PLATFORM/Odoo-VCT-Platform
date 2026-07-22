import { Message } from "@mail/core/common/message";
import { Typing } from "@mail/discuss/typing/common/typing";
import { patch } from "@web/core/utils/patch";
import { onMounted, onPatched } from "@odoo/owl";

const sessionStartTime = Date.now();
const animatedMessageIds = new Set();

// 1. Customize Typing indicator text to show "Trợ lý AI đang suy nghĩ..."
patch(Typing.prototype, {
    get text() {
        const typingMemberNames = this.props.member
            ? [this.props.member.name]
            : (this.props.channel?.otherTypingMembers || []).map(({ name }) => name);

        if (typingMemberNames.length === 1) {
            const firstName = (typingMemberNames[0] || "").toLowerCase();
            if (firstName.includes("trợ lý ai") || firstName.includes("odoobot") || firstName.includes("ai assistant")) {
                return "Trợ lý AI đang suy nghĩ...";
            }
        }
        return super.text;
    }
});

// 2. Patch Message component for smooth Typewriter streaming on NEW AI replies only
patch(Message.prototype, {
    setup() {
        super.setup();

        const triggerTypewriter = () => {
            this._runTypewriterEffect();
        };

        onMounted(triggerTypewriter);
        onPatched(triggerTypewriter);
    },

    _runTypewriterEffect() {
        const msg = this.props?.message;
        if (!msg || !msg.id || animatedMessageIds.has(msg.id)) {
            return;
        }

        const authorName = (msg.authorName || "").toLowerCase();
        const isAi = authorName.includes("trợ lý ai") || authorName.includes("odoobot") || authorName.includes("ai assistant");
        if (!isAi) {
            return;
        }

        const rootEl = this.root?.el;
        if (!rootEl) {
            return;
        }

        const bodyEl = rootEl.querySelector(".o-mail-Message-body") || rootEl.querySelector(".o-mail-Message-richBody");
        if (!bodyEl) {
            return;
        }

        if (bodyEl.dataset.typewriterDone === "true") {
            return;
        }

        // Check message date: Only animate if created AFTER the current session loaded (within last 10 seconds)
        const msgDateMs = msg.date?.toMillis ? msg.date.toMillis() : (msg.date ? new Date(msg.date).getTime() : 0);
        const isOldMessage = msgDateMs > 0 && msgDateMs < (sessionStartTime - 10000);

        if (isOldMessage) {
            animatedMessageIds.add(msg.id);
            bodyEl.dataset.typewriterDone = "true";
            return;
        }

        const fullHTML = bodyEl.innerHTML;
        const textContent = bodyEl.textContent || bodyEl.innerText || "";
        if (!textContent.trim() || textContent.length < 2) {
            return;
        }

        animatedMessageIds.add(msg.id);
        bodyEl.dataset.typewriterDone = "true";
        bodyEl.classList.add("o_ai_typewriter_active");

        // Clone DOM tree to type out text nodes while preserving HTML elements
        const clone = bodyEl.cloneNode(true);
        const textNodes = [];
        const walker = document.createTreeWalker(clone, NodeFilter.SHOW_TEXT, null, false);
        let n;
        while ((n = walker.nextNode())) {
            if (n.nodeValue && n.nodeValue.trim()) {
                textNodes.push({ node: n, targetText: n.nodeValue, targetLength: n.nodeValue.length });
                n.nodeValue = "";
            }
        }

        if (textNodes.length === 0) {
            bodyEl.classList.remove("o_ai_typewriter_active");
            return;
        }

        bodyEl.innerHTML = "";
        while (clone.firstChild) {
            bodyEl.appendChild(clone.firstChild);
        }

        const cursorSpan = document.createElement("span");
        cursorSpan.className = "o_ai_typewriter_cursor";
        cursorSpan.textContent = "▋";
        bodyEl.appendChild(cursorSpan);

        const speed = 10;
        const interval = setInterval(() => {
            // If element was detached by OWL re-render
            if (!document.body.contains(bodyEl)) {
                clearInterval(interval);
                return;
            }

            let done = true;
            for (let i = 0; i < textNodes.length; i++) {
                const item = textNodes[i];
                if (item.node.nodeValue.length < item.targetLength) {
                    const addChars = Math.min(4, item.targetLength - item.node.nodeValue.length);
                    item.node.nodeValue += item.targetText.substring(
                        item.node.nodeValue.length,
                        item.node.nodeValue.length + addChars
                    );
                    done = false;
                    break;
                }
            }

            const threadEl = rootEl.closest(".o-mail-Thread");
            if (threadEl) {
                threadEl.scrollTop = threadEl.scrollHeight;
            }

            if (done) {
                clearInterval(interval);
                if (cursorSpan.parentNode) {
                    cursorSpan.parentNode.removeChild(cursorSpan);
                }
                bodyEl.innerHTML = fullHTML;
                bodyEl.classList.remove("o_ai_typewriter_active");
            }
        }, speed);
    }
});
