function setupChatPanel({ formId, inputId, boxId, loadingId, clearBtnId, askEndpoint, clearEndpoint }) {
    const form = document.getElementById(formId);
    const input = document.getElementById(inputId);
    const chatBox = document.getElementById(boxId);
    const loading = document.getElementById(loadingId);
    const clearBtn = document.getElementById(clearBtnId);

    form.onsubmit = async (e) => {
        e.preventDefault();
        const userText = input.value.trim();
        if (!userText) return;

        // 1. Append user message bubble
        const userBubble = document.createElement("div");
        userBubble.className = "chat-msg user-msg";
        userBubble.innerText = userText;
        chatBox.appendChild(userBubble);
        chatBox.scrollTop = chatBox.scrollHeight;

        const formData = new FormData(e.target);
        input.value = "";
        loading.style.display = "block";

        // 2. Fetch AI reply
        const res = await fetch(askEndpoint, {
            method: "POST",
            body: formData
        });
        const data = await res.json();
        loading.style.display = "none";

        // 3. Append AI message bubble
        const botBubble = document.createElement("div");
        botBubble.className = "chat-msg bot-msg";
        botBubble.innerHTML = marked.parse(data.response);

        // Show retrieved chunk badge if RAG returned matches
        if (data.sources_count !== undefined && data.sources_count > 0) {
            const sourceTag = document.createElement("div");
            sourceTag.className = "rag-sources";
            sourceTag.innerText = `📚 Grounded using ${data.sources_count} retrieved chunk(s) from knowledge base`;
            botBubble.appendChild(sourceTag);
        }

        chatBox.appendChild(botBubble);
        chatBox.scrollTop = chatBox.scrollHeight;
    };

    clearBtn.onclick = async () => {
        await fetch(clearEndpoint, { method: "POST" });
        chatBox.innerHTML = "";
    };
}

// Left Panel: Without RAG
setupChatPanel({
    formId: "askFormNormal",
    inputId: "questionInputNormal",
    boxId: "chat-box-normal",
    loadingId: "ans-loading-normal",
    clearBtnId: "clearChatNormalBtn",
    askEndpoint: "/ask",
    clearEndpoint: "/clear_chat"
});

// Right Panel: With RAG
setupChatPanel({
    formId: "askFormRag",
    inputId: "questionInputRag",
    boxId: "chat-box-rag",
    loadingId: "ans-loading-rag",
    clearBtnId: "clearChatRagBtn",
    askEndpoint: "/ask_rag",
    clearEndpoint: "/clear_chat_rag"
});

// Email Summarizer
document.getElementById("emailForm").onsubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);

    const loading = document.getElementById("summary-loading");
    loading.style.display = "block";

    const res = await fetch("/summarize", {
        method: "POST",
        body: formData
    });

    const data = await res.json();
    document.getElementById("summary").innerHTML = marked.parse(data.response);
    loading.style.display = "none";
};

// Document Extractor
document.getElementById("extractForm").onsubmit = async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);

    const loading = document.getElementById("extract-loading");
    const analysisBox = document.getElementById("extract-analysis");
    const rawDetails = document.getElementById("raw-data-details");
    const rawBox = document.getElementById("extracted-raw");

    loading.style.display = "block";
    analysisBox.style.display = "none";
    rawDetails.style.display = "none";

    const res = await fetch("/extract", {
        method: "POST",
        body: formData
    });

    const data = await res.json();
    loading.style.display = "none";

    if (data.response) {
        analysisBox.innerHTML = marked.parse(data.response);
        analysisBox.style.display = "block";
    } else {
        analysisBox.innerHTML = marked.parse(data.analysis);
        analysisBox.style.display = "block";
        rawBox.innerText = data.extracted_text;
        rawDetails.style.display = "block";
    }
};