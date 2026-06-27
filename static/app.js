/* ============================================================
   State
   ============================================================ */
const state = {
    allLinks: [], // { url: string, filename: string }
    totalActIds: 0, // 批量查询总数
    successActIds: 0, // 成功数
    failActIds: 0, // 失败数
};

/* ============================================================
   Pagination state
   ============================================================ */
const PAGE_CARD_LIMIT = 200; // 每页卡牌数量阈值

// page 数据结构：{ collections: [], cardCount: 0, fetched: false }
// 初始化时自动创建第 0 页
window._pages = [{ collections: [], cardCount: 0 }];
window._currentPageIdx = 0;
window._pendingActIds = [];   // 尚未取回的 act_id（下一页继续）
window._pendingOpts = null;   // 当前批次的 opts
window._isPageFetching = false; // 是否正在加载中

/* ============================================================
   Utility: parse comma-separated act_id list
   ============================================================ */
function parseActIds(raw) {
    if (!raw || !raw.trim()) return [];
    // 统一分隔符：中文逗号、顿号、分号、空格、换行 -> 英文逗号
    const normalized = raw
        .replace(/[；;]\s*|[，、]/g, ',')
        .replace(/[\s\n\r]+/g, ',')
        .replace(/,+/g, ',');
    const ids = normalized.split(',')
        .map(function (s) { return s.trim(); })
        .filter(function (s) { return s && /^\d+$/.test(s) && s !== '0'; });
    var seen = new Set();
    return ids.filter(function (id) {
        if (seen.has(id)) return false;
        seen.add(id);
        return true;
    });
}

/* ============================================================
   Toast notification
   ============================================================ */
var toastTimer = null;

function showToast(message, isError) {
    var el = document.getElementById("toast");
    if (!el) return;
    if (toastTimer) { clearTimeout(toastTimer); el.classList.remove("show", "error"); }
    el.textContent = message;
    if (isError) el.classList.add("error"); else el.classList.remove("error");
    // Force reflow
    void el.offsetWidth;
    el.classList.add("show");
    toastTimer = setTimeout(function () {
        el.classList.remove("show", "error");
        toastTimer = null;
    }, 2200);
}

/* ============================================================
   QR code handling
   ============================================================ */
const qrInput = document.getElementById("qr-input");
const qrZone = document.getElementById("qr-zone");
const qrThumbs = document.getElementById("qr-thumbs");

qrInput.addEventListener("change", (e) => processQrFiles(e.target.files));

qrZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    qrZone.classList.add("over");
});
qrZone.addEventListener("dragleave", () =>
    qrZone.classList.remove("over"),
);
qrZone.addEventListener("drop", (e) => {
    e.preventDefault();
    qrZone.classList.remove("over");
    processQrFiles(e.dataTransfer.files);
});

/**
 * Extract act_id from a raw string.
 * 1. If it's a URL with act_id in the query string, return it directly.
 * 2. If it's a bare number, return it directly.
 * 3. Otherwise (e.g. b23.tv short link), ask the backend to follow redirects
 *    and try extracting act_id from the final URL.
 */
async function extractActId(text) {
    text = text.trim();
    // Direct URL with act_id param
    try {
        const actId = new URL(text).searchParams.get("act_id");
        if (actId) return actId;
    } catch (_) { }
    // Bare number
    if (/^\d+$/.test(text)) return text;
    // HTTP(S) URL without act_id — may be a short link; resolve via backend
    if (/^https?:\/\//i.test(text)) {
        try {
            const res = await fetch(
                `${API_BASE}/api/resolve_url?url=${encodeURIComponent(text)}`,
            );
            const json = await res.json();
            if (json.code === 0 && json.url) {
                const actId = new URL(json.url).searchParams.get("act_id");
                if (actId) return actId;
            }
        } catch (_) { }
    }
    return null;
}

function processQrFiles(files) {
    Array.from(files).forEach((file) => {
        const reader = new FileReader();
        reader.onload = (ev) => {
            const img = new Image();
            img.onload = async () => {
                const canvas = document.createElement("canvas");
                canvas.width = img.width;
                canvas.height = img.height;
                canvas.getContext("2d").drawImage(img, 0, 0);
                const imgData = canvas
                    .getContext("2d")
                    .getImageData(0, 0, img.width, img.height);
                const code = jsQR(imgData.data, imgData.width, imgData.height);

                // Add a "resolving…" placeholder badge while we await
                const thumb = document.createElement("div");
                thumb.className = "qr-thumb";
                const imgEl = document.createElement("img");
                imgEl.src = ev.target.result;
                thumb.appendChild(imgEl);
                const badge = document.createElement("div");
                badge.className = "qr-badge";
                badge.textContent = code ? "⏳ 解析中…" : "✗ 未识别";
                thumb.appendChild(badge);
                qrThumbs.appendChild(thumb);

                if (!code || !code.data) {
                    thumb.classList.add("fail");
                    return;
                }

                const actId = await extractActId(code.data);

                thumb.classList.add(actId ? "ok" : "fail");
                badge.textContent = actId ? "✓ act_id=" + actId : "✗ 无 act_id";

                if (actId) {
                    // 追加到已有 act_id 列表（去重）
                    var existing = parseActIds(document.getElementById("act-id-input").value);
                    if (existing.indexOf(actId) === -1) existing.push(actId);
                    document.getElementById("act-id-input").value = existing.join(", ");
                    startFetch();
                }
            };
            img.src = ev.target.result;
        };
        reader.readAsDataURL(file);
    });
}

/* ============================================================
   API
   ============================================================ */
async function fetchCollection(act_id, lottery_id) {
    const res = await fetch(
        `${API_BASE}/api/fetch?act_id=${encodeURIComponent(act_id)}&lottery_id=${encodeURIComponent(lottery_id)}`,
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

/* ============================================================
   Parse API data
   ============================================================ */
function parseData(data, opts) {
    const name = data.name || "未知收藏集";
    const map = new Map(); // card_name → { card_name, links[] }

    function processCard(card) {
        if (!card) return;
        const cn = card.card_name || "unnamed";
        if (!map.has(cn)) map.set(cn, { card_name: cn, links: [] });
        const entry = map.get(cn);

        if (opts.img && card.card_img)
            entry.links.push({
                url: card.card_img,
                label: "🖼️",
                cls: "dl-a-img",
                ext: "png",
            });

        if (opts.vid && card.video_list && card.video_list[0])
            entry.links.push({
                url: card.video_list[0],
                label: "🎬",
                cls: "dl-a-vid",
                ext: "mp4",
            });

        if (
            opts.wm &&
            card.video_list_download &&
            card.video_list_download[0]
        )
            entry.links.push({
                url: card.video_list_download[0],
                label: "💧",
                cls: "dl-a-wm",
                ext: "mp4",
            });
    }

    // processCardTypeInfo handles the collect_infos path whose card_type_info object
    // uses a different schema from card_info: name/overview_image/content.animation/watermark_animations.
    function processCardTypeInfo(cti) {
        if (!cti) return;
        const cn = cti.name || "unnamed";
        if (!map.has(cn)) map.set(cn, { card_name: cn, links: [] });
        const entry = map.get(cn);

        const img =
            cti.overview_image ||
            (cti.content &&
                cti.content.animation &&
                cti.content.animation.animation_first_frame) ||
            null;
        if (opts.img && img)
            entry.links.push({
                url: img,
                label: "🖼️",
                cls: "dl-a-img",
                ext: "png",
            });

        const vid =
            (cti.content &&
                cti.content.animation &&
                cti.content.animation.animation_video_urls &&
                cti.content.animation.animation_video_urls[0]) ||
            null;
        if (opts.vid && vid)
            entry.links.push({
                url: vid,
                label: "🎬",
                cls: "dl-a-vid",
                ext: "mp4",
            });

        const wm =
            (cti.watermark_animations &&
                cti.watermark_animations[0] &&
                cti.watermark_animations[0].watermark_animation) ||
            null;
        if (opts.wm && wm)
            entry.links.push({
                url: wm,
                label: "💧",
                cls: "dl-a-wm",
                ext: "mp4",
            });
    }

    (data.item_list || []).forEach(
        (item) => item && processCard(item.card_info),
    );

    var cl = data.collect_list;
    if (cl) {
        if (Array.isArray(cl)) {
            cl.forEach(function (c) {
                if (c && c.card_item && c.card_item.card_type_info)
                    processCardTypeInfo(c.card_item.card_type_info);
            });
        } else if (typeof cl === "object") {
            (cl.collect_infos || []).forEach(function (c) {
                if (c && c.card_item && c.card_item.card_type_info)
                    processCardTypeInfo(c.card_item.card_type_info);
            });
        }
    }

    return { name: name, cards: [...map.values()] };
}

/* ============================================================
   Progress helpers
   ============================================================ */
function setProgress(pct, text) {
    document.getElementById("prog-bar").style.width = pct + "%";
    document.getElementById("prog-text").textContent = text;
}
function showProgress() {
    document.getElementById("prog-wrap").classList.add("on");
}
function hideProgress() {
    document.getElementById("prog-wrap").classList.remove("on");
}

/* ============================================================
   Alert helpers
   ============================================================ */
function addAlert(cls, html) {
    const d = document.createElement("div");
    d.className = "alert " + cls;
    d.innerHTML = html;
    document.getElementById("alerts").appendChild(d);
}
function clearAlerts() {
    document.getElementById("alerts").innerHTML = "";
}

/* ============================================================
   Render results
   ============================================================ */
function renderResults(collections) {
    const container = document.getElementById("results-body");
    container.innerHTML = "";
    state.allLinks = [];

    if (!collections.length) {
        container.innerHTML =
            '<div class="empty"><div class="icon">😕</div><p>未找到可下载内容</p></div>';
        return;
    }

    const safeName = (s) => s.replace(/[<>:"/\\|?*\s]/g, "_");

    for (const coll of collections) {
        const block = document.createElement("div");
        block.className = "coll-block card";

        // ── Header (点击切换折叠) ──
        const header = document.createElement("div");
        header.className = "coll-header";
        header.setAttribute("role", "button");
        header.setAttribute("tabindex", "0");
        header.setAttribute("aria-expanded", "true");

        const toggle = document.createElement("span");
        toggle.className = "coll-toggle";
        toggle.textContent = "▼";

        const nameSpan = document.createElement("span");
        nameSpan.className = "coll-name";
        nameSpan.textContent = coll.name;

        const subSpan = document.createElement("span");
        subSpan.className = "coll-sub";
        subSpan.textContent = "共 " + coll.cards.length + " 个卡牌";

        header.appendChild(toggle);
        header.appendChild(nameSpan);
        header.appendChild(subSpan);

        // ── 右上 B 站跳转链接 ──
        var link = document.createElement("a");
        link.className = "coll-link";
        link.href = "https://www.bilibili.com/h5/mall/digital-card/home?act_id=" + coll.actId;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.title = "在 B 站打开 " + coll.name;
        link.textContent = "🔗";
        block.appendChild(link);

        // ── Body (可折叠) ──
        const body = document.createElement("div");
        body.className = "coll-body";

        const list = document.createElement("div");
        list.className = "dl-list";

        for (const card of coll.cards) {
            const item = document.createElement("div");
            item.className = "dl-item";

            // 顶部：标题+tab
            const top = document.createElement("div");
            top.className = "dl-item-top";

            const nm = document.createElement("div");
            nm.className = "dl-item-name";
            nm.title = card.card_name;
            nm.textContent = card.card_name;
            top.appendChild(nm);

            // tabs
            const tabs = document.createElement("div");
            tabs.className = "dl-tabs";
            // 收集类型
            const types = [];
            for (const dl of card.links) {
                if (dl.cls === "dl-a-img" && !types.includes("img"))
                    types.push("img");
                if (dl.cls === "dl-a-vid" && !types.includes("vid"))
                    types.push("vid");
                if (dl.cls === "dl-a-wm" && !types.includes("wm"))
                    types.push("wm");
            }
            // tab标签
            const tabNames = { img: "🖼️", vid: "🎬", wm: "💧" };
            let activeType = types[0] || "img";
            types.forEach((type) => {
                const tab = document.createElement("div");
                tab.className = "dl-tab" + (type === activeType ? " active" : "");
                tab.textContent = tabNames[type] || type;
                tab.dataset.type = type;
                tab.onclick = () => {
                    activeType = type;
                    [...tabs.children].forEach((t) =>
                        t.classList.toggle("active", t.dataset.type === type),
                    );
                    renderPreview();
                };
                tabs.appendChild(tab);
            });
            top.appendChild(tabs);
            item.appendChild(top);

            // 预览区
            const preview = document.createElement("div");
            preview.className = "dl-preview";
            function renderPreview() {
                preview.innerHTML = "";
                let hasContent = false;
                // 去重：避免同一类型相同 URL 被渲染多次
                const seen = new Set();
                for (const dl of card.links) {
                    const key = (dl.cls || "") + "|" + (dl.url || "");
                    if (seen.has(key)) continue;
                    seen.add(key);

                    if (activeType === "img" && dl.cls === "dl-a-img") {
                        const img = document.createElement("img");
                        // 使用后端代理加载图片，避免浏览器长按保存为 HTML（代理需返回正确的 image/* Content-Type）
                        img.src = `${API_BASE}/api/proxy_img?url=${encodeURIComponent(dl.url)}`;
                        img.alt = "图片预览";
                        img.loading = "lazy";
                        img.referrerPolicy = "no-referrer";
                        preview.appendChild(img);
                        hasContent = true;
                    } else if (activeType === "vid" && dl.cls === "dl-a-vid") {
                        const video = document.createElement("video");
                        video.src = dl.url;
                        video.controls = true;
                        video.preload = "none";
                        preview.appendChild(video);
                        hasContent = true;
                    } else if (activeType === "wm" && dl.cls === "dl-a-wm") {
                        const video = document.createElement("video");
                        video.src = dl.url;
                        video.controls = true;
                        video.preload = "none";
                        preview.appendChild(video);
                        hasContent = true;
                    }
                }
                if (!hasContent) {
                    preview.innerHTML =
                        '<span style="color:#bbb;font-size:13px;">无可用预览</span>';
                }
            }
            renderPreview();
            item.appendChild(preview);

            for (const dl of card.links) {
                let filename = safeName(card.card_name);
                // 如果是带水印视频，文件名结尾加"水印"
                if (dl.cls === "dl-a-wm") {
                    filename += "-水印";
                }
                filename += "." + dl.ext;
                state.allLinks.push({
                    url: dl.url,
                    filename: filename,
                    type: dl.cls, // 标记类型
                    collectionFolder: safeName(coll.name || "未知合集"),
                });
            }

            list.appendChild(item);
        }

        body.appendChild(list);

        // ── 底部收起按钮 ──
        var collapseBtn = document.createElement("div");
        collapseBtn.className = "coll-bottom-btn";
        collapseBtn.textContent = "▲ 收起";
        body.appendChild(collapseBtn);

        block.appendChild(header);
        block.appendChild(body);

        // ── 切换折叠 ──
        const toggleCollapse = function () {
            var wasClosed = body.classList.contains("closed");
            if (wasClosed) {
                // 展开
                body.style.maxHeight = body.scrollHeight + "px";
                body.classList.remove("closed");
                toggle.classList.remove("collapsed");
                header.classList.remove("collapsed");
                header.setAttribute("aria-expanded", "true");
            } else {
                // 折叠
                body.style.maxHeight = body.scrollHeight + "px";
                void body.offsetHeight;
                body.classList.add("closed");
                body.style.maxHeight = "0";
                toggle.classList.add("collapsed");
                header.classList.add("collapsed");
                header.setAttribute("aria-expanded", "false");
            }
        };

        header.addEventListener("click", toggleCollapse);
        collapseBtn.addEventListener("click", function (e) { e.stopPropagation(); toggleCollapse(); });

        container.appendChild(block);

        // ── 初始高度：先挂到 DOM 再读取 scrollHeight，否则值为 0 ──
        void block.offsetHeight; // 强制回流确保布局已计算
        body.style.maxHeight = body.scrollHeight + "px";
    }

    if (state.allLinks.length > 0) {
        document.getElementById("btn-dl-all").style.display = "inline-flex";
        document.getElementById("dl-type-chks").style.display = "flex";
        // 默认与上方选项同步
        document.getElementById("dl-chk-img").checked =
            document.getElementById("opt-img").checked;
        document.getElementById("dl-chk-vid").checked =
            document.getElementById("opt-vid").checked;
        document.getElementById("dl-chk-wm").checked =
            document.getElementById("opt-wm").checked;
    } else {
        document.getElementById("dl-type-chks").style.display = "none";
    }

    updateActionButtons();
}

function updateActionButtons() {
    var hasLinks = state.allLinks.length > 0;
    var hasSucceeded = window._succeededActIds && window._succeededActIds.size > 0;
    var shareBtn = document.getElementById("btn-share");
    var clearBtn = document.getElementById("btn-clear");
    if (shareBtn) {
        shareBtn.classList.toggle("btn-available", !!hasSucceeded);
        shareBtn.disabled = !hasSucceeded;
    }
    if (clearBtn) {
        clearBtn.classList.toggle("ghost-available", !!hasLinks);
        clearBtn.disabled = !hasLinks;
    }
}

function escHtml(s) {
    return s
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

function isAppMode() {
    try {
        if (typeof window.pywebview !== "undefined") return true;
    } catch (e) { }
    try {
        const params = new URLSearchParams(location.search);
        if (params.get("app") === "1") return true;
    } catch (e) { }
    return false;
}

/* ============================================================
   Pagination helpers
   ============================================================ */

function getCurrentPageData() {
    return window._pages[window._currentPageIdx] || { collections: [], cardCount: 0 };
}

function getTotalPages() {
    return window._pages.length;
}

function updatePaginationUI() {
    var pagEl = document.getElementById("pagination");
    var infoEl = document.getElementById("page-info");
    var prevBtn = document.getElementById("btn-page-prev");
    var nextBtn = document.getElementById("btn-page-next");

    var curIdx = window._currentPageIdx;
    var totalPages = getTotalPages();
    var curPage = getCurrentPageData();
    var allDone = window._pendingActIds.length === 0 && !window._isPageFetching;
    var hasPending = window._pendingActIds.length > 0;

    if (totalPages <= 1 && allDone) {
        pagEl.style.display = "none";
        return;
    }

    pagEl.style.display = "flex";
    infoEl.textContent = "第 " + (curIdx + 1) + " / " + totalPages + " 页 · " + curPage.cardCount + " 张";

    prevBtn.disabled = curIdx === 0;

    if (allDone && curIdx === totalPages - 1) {
        nextBtn.disabled = true;
        nextBtn.textContent = "完毕";
    } else if (window._isPageFetching) {
        nextBtn.disabled = true;
        nextBtn.textContent = "加载中…";
    } else if (hasPending) {
        nextBtn.disabled = false;
        nextBtn.textContent = "下一页 ▶";
    } else {
        nextBtn.disabled = false;
        nextBtn.textContent = "下一页 ▶";
    }
}

/* ============================================================
   Load progress line (compact, single line)
   ============================================================ */
function updateLoadProgress() {
    var el = document.getElementById("load-progress");
    if (!el) {
        el = document.createElement("div");
        el.id = "load-progress";
        el.className = "load-progress";
        var alerts = document.getElementById("alerts");
        alerts.insertBefore(el, alerts.firstChild);
    }
    var totalCards = 0;
    var totalColls = 0;
    for (var pi = 0; pi < window._pages.length; pi++) {
        var pg = window._pages[pi];
        totalCards += pg.cardCount;
        totalColls += pg.collections.length;
    }
    var pending = window._pendingActIds ? window._pendingActIds.length : 0;
    var text = "📦 " + totalColls + " 合集 · " + totalCards + " 张";
    if (pending > 0) {
        text += " · 剩余 " + pending;
    }
    el.textContent = text;
}

function renderCurrentPage() {
    var container = document.getElementById("results-body");
    container.innerHTML = "";
    state.allLinks = [];

    var pageData = getCurrentPageData();
    if (!pageData.collections.length) {
        container.innerHTML =
            '<div class="empty"><div class="icon">😕</div><p>此页暂无内容</p></div>';
        updatePaginationUI();
        updateActionButtons();
        return;
    }

    // 渲染当前页所有收藏集
    for (var ci = 0; ci < pageData.collections.length; ci++) {
        appendSingleBlock(container, pageData.collections[ci]);
    }

    updatePaginationUI();
    updateActionButtons();
}

async function nextPage() {
    var curIdx = window._currentPageIdx;
    var totalPages = getTotalPages();

    // 翻到下一页
    if (curIdx < totalPages - 1) {
        window._currentPageIdx++;
        renderCurrentPage();
        // 如果还有待加载且未在加载中，在新页开始加载
        if (window._pendingActIds.length > 0 && !window._isPageFetching) {
            continueFetch();
        }
    }
}

function prevPage() {
    if (window._currentPageIdx > 0) {
        window._currentPageIdx--;
        renderCurrentPage();
    }
}

/* ============================================================
   Append a single collection block to container
   ============================================================ */
function appendSingleBlock(container, coll) {
    if (!coll || !coll.cards || !coll.cards.length) return;

    const block = document.createElement("div");
    block.className = "coll-block card";

    // ── Header ──
    const header = document.createElement("div");
    header.className = "coll-header";
    header.setAttribute("role", "button");
    header.setAttribute("tabindex", "0");
    header.setAttribute("aria-expanded", "true");

    const toggle = document.createElement("span");
    toggle.className = "coll-toggle";
    toggle.textContent = "▼";

    const nameSpan = document.createElement("span");
    nameSpan.className = "coll-name";
    nameSpan.textContent = coll.name;

    const subSpan = document.createElement("span");
    subSpan.className = "coll-sub";
    subSpan.textContent = "共 " + coll.cards.length + " 个卡牌";

    header.appendChild(toggle);
    header.appendChild(nameSpan);
    header.appendChild(subSpan);

    // ── B站跳转链接 ──
    var link = document.createElement("a");
    link.className = "coll-link";
    link.href = "https://www.bilibili.com/h5/mall/digital-card/home?act_id=" + coll.actId;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.title = "在 B 站打开 " + coll.name;
    link.textContent = "🔗";
    block.appendChild(link);

    // ── Body ──
    const body = document.createElement("div");
    body.className = "coll-body";

    const list = document.createElement("div");
    list.className = "dl-list";

    const safeName = (s) => s.replace(/[<>:"/\\|?*\s]/g, "_");

    for (const card of coll.cards) {
        const item = document.createElement("div");
        item.className = "dl-item";

        const top = document.createElement("div");
        top.className = "dl-item-top";

        const nm = document.createElement("div");
        nm.className = "dl-item-name";
        nm.title = card.card_name;
        nm.textContent = card.card_name;
        top.appendChild(nm);

        const tabs = document.createElement("div");
        tabs.className = "dl-tabs";
        const types = [];
        for (const dl of card.links) {
            if (dl.cls === "dl-a-img" && !types.includes("img")) types.push("img");
            if (dl.cls === "dl-a-vid" && !types.includes("vid")) types.push("vid");
            if (dl.cls === "dl-a-wm" && !types.includes("wm")) types.push("wm");
        }
        const tabNames = { img: "🖼️", vid: "🎬", wm: "💧" };
        let activeType = types[0] || "img";
        types.forEach((type) => {
            const tab = document.createElement("div");
            tab.className = "dl-tab" + (type === activeType ? " active" : "");
            tab.textContent = tabNames[type] || type;
            tab.dataset.type = type;
            tab.onclick = () => {
                activeType = type;
                [...tabs.children].forEach((t) =>
                    t.classList.toggle("active", t.dataset.type === type)
                );
                renderPreview();
            };
            tabs.appendChild(tab);
        });
        top.appendChild(tabs);
        item.appendChild(top);

        const preview = document.createElement("div");
        preview.className = "dl-preview";
        function renderPreview() {
            preview.innerHTML = "";
            let hasContent = false;
            const seen = new Set();
            for (const dl of card.links) {
                const key = (dl.cls || "") + "|" + (dl.url || "");
                if (seen.has(key)) continue;
                seen.add(key);
                if (activeType === "img" && dl.cls === "dl-a-img") {
                    const img = document.createElement("img");
                    img.src = `${API_BASE}/api/proxy_img?url=${encodeURIComponent(dl.url)}`;
                    img.alt = "图片预览";
                    img.loading = "lazy";
                    img.referrerPolicy = "no-referrer";
                    preview.appendChild(img);
                    hasContent = true;
                } else if (activeType === "vid" && dl.cls === "dl-a-vid") {
                    const video = document.createElement("video");
                    video.src = dl.url;
                    video.controls = true;
                    video.preload = "none";
                    preview.appendChild(video);
                    hasContent = true;
                } else if (activeType === "wm" && dl.cls === "dl-a-wm") {
                    const video = document.createElement("video");
                    video.src = dl.url;
                    video.controls = true;
                    video.preload = "none";
                    preview.appendChild(video);
                    hasContent = true;
                }
            }
            if (!hasContent) {
                preview.innerHTML =
                    '<span style="color:#bbb;font-size:13px;">无可用预览</span>';
            }
        }
        renderPreview();
        item.appendChild(preview);

        for (const dl of card.links) {
            let filename = safeName(card.card_name);
            if (dl.cls === "dl-a-wm") {
                filename += "-水印";
            }
            filename += "." + dl.ext;
            state.allLinks.push({
                url: dl.url,
                filename: filename,
                type: dl.cls,
                collectionFolder: safeName(coll.name || "未知合集"),
            });
        }
        list.appendChild(item);
    }

    body.appendChild(list);

    var collapseBtn = document.createElement("div");
    collapseBtn.className = "coll-bottom-btn";
    collapseBtn.textContent = "▲ 收起";
    body.appendChild(collapseBtn);

    block.appendChild(header);
    block.appendChild(body);

    var collapseTimer = null;
    const toggleCollapse = function () {
        if (collapseTimer) { clearTimeout(collapseTimer); collapseTimer = null; }
        var wasClosed = body.classList.contains("closed");
        if (wasClosed) {
            body.style.maxHeight = body.scrollHeight + "px";
            body.classList.remove("closed");
            toggle.classList.remove("collapsed");
            header.classList.remove("collapsed");
            header.setAttribute("aria-expanded", "true");
            // 过渡结束后移除固定 max-height，内容变化时不会被裁剪
            collapseTimer = setTimeout(function () {
                body.style.maxHeight = "";
                collapseTimer = null;
            }, 360);
        } else {
            body.style.maxHeight = body.scrollHeight + "px";
            void body.offsetHeight;
            body.classList.add("closed");
            body.style.maxHeight = "0";
            toggle.classList.add("collapsed");
            header.classList.add("collapsed");
            header.setAttribute("aria-expanded", "false");
        }
    };
    header.addEventListener("click", toggleCollapse);
    collapseBtn.addEventListener("click", function (e) { e.stopPropagation(); toggleCollapse(); });

    container.appendChild(block);
}

/* ============================================================
   Main: start fetch (incremental loading with pagination)
   ============================================================ */
async function startFetch() {
    var raw = document.getElementById("act-id-input").value.trim();
    if (!raw) {
        clearAlerts();
        document.getElementById("results-wrap").classList.add("on");
        addAlert("alert-warn", "⚠️ 请输入至少一个 act_id（纯数字），多个用英文逗号分隔。");
        return;
    }

    // Try direct parsing first
    var actIds = parseActIds(raw);
    if (!actIds.length) {
        var single = await extractActId(raw);
        if (single) actIds = parseActIds(single);
    }

    if (!actIds.length) {
        clearAlerts();
        document.getElementById("results-wrap").classList.add("on");
        addAlert("alert-warn", "⚠️ 请输入有效的 <code>act_id</code>（纯数字）、含 <code>act_id</code> 参数的完整链接，或 b23.tv 短链接。支持多个用英文逗号分隔。");
        return;
    }

    // 去重
    if (!window._queriedActIds) window._queriedActIds = new Set();
    var newActIds = actIds.filter(function (id) {
        if (window._queriedActIds.has(id)) return false;
        window._queriedActIds.add(id);
        return true;
    });

    if (!newActIds.length) {
        clearAlerts();
        document.getElementById("results-wrap").classList.add("on");
        addAlert("alert-warn", "⚠️ 这些 act_id 都已经查询过了。");
        return;
    }

    window._batchSkippedCount = actIds.length - newActIds.length;

    var opts = {
        img: document.getElementById("opt-img").checked,
        vid: document.getElementById("opt-vid").checked,
        wm: document.getElementById("opt-wm").checked,
    };

    // ── 重置分页状态 ──
    window._pages = [{ collections: [], cardCount: 0 }];
    window._currentPageIdx = 0;
    window._pendingActIds = newActIds.slice(); // 剩余待取回的 act_id
    window._pendingOpts = opts;
    window._isPageFetching = false;

    // ── UI 准备 ──
    var btn = document.getElementById("btn-start");
    btn.disabled = true;
    showProgress();
    document.getElementById("results-wrap").classList.add("on");
    clearAlerts();
    document.getElementById("results-body").innerHTML = "";
    document.getElementById("btn-dl-all").style.display = "none";
    document.getElementById("pagination").style.display = "none";

    // 累计：不清空已有集合
    if (!window._allCollections) window._allCollections = [];

    // 显示紧凑进度
    updateLoadProgress();
    // 开始加载第一页
    await continueFetch();
}

/* ============================================================
   continueFetch: 加载下一页 / 继续加载当前批次的剩余 act_id
   ============================================================ */
async function continueFetch() {
    if (window._isPageFetching) return;
    window._isPageFetching = true;

    var totalSteps = window._pendingActIds.length + window._allCollections.length;
    var opts = window._pendingOpts;
    var btn = document.getElementById("btn-start");

    // 当前页 —— 可能已经有上一页的部分数据（翻页回来时）
    var curPage = getCurrentPageData();
    // 如果当前页已有数据且不是最后一页，先翻到下一页
    if (curPage.collections.length > 0 && window._currentPageIdx < getTotalPages() - 1) {
        window._currentPageIdx++;
        curPage = getCurrentPageData();
    }

    state.totalActIds = window._pendingActIds.length;
    state.successActIds = 0;
    state.failActIds = 0;

    var pageFetchedCount = 0;

    // 逐个取回 act_id
    while (window._pendingActIds.length > 0) {
        var actId = window._pendingActIds[0];
        var doneSoFar = window._allCollections.length;
        var progressBase = 5 + (doneSoFar / totalSteps) * 85;

        setProgress(Math.round(progressBase), "正在查询分组：act_id=" + actId + " (" + (doneSoFar + 1) + "/" + totalSteps + ")…");

        // Step 1: get_params
        var allParams;
        try {
            var paramsRes = await fetch(API_BASE + "/api/get_params?act_id=" + encodeURIComponent(actId));
            var paramsJson = await paramsRes.json();
            if (paramsJson.code !== 0) {
                state.failActIds++;
                addAlert("alert-err", "❌ 分组查询失败 (act_id=" + escHtml(actId) + "): " + escHtml(String(paramsJson.message || paramsJson.code)));
                window._pendingActIds.shift();
                continue;
            }
            allParams = paramsJson.data || [];
        } catch (err) {
            state.failActIds++;
            addAlert("alert-err", "❌ 分组查询失败 (act_id=" + escHtml(actId) + "): " + escHtml(err.message || String(err)));
            window._pendingActIds.shift();
            continue;
        }

        if (!allParams.length) {
            state.failActIds++;
            addAlert("alert-warn", "⚠️ 未找到收藏集分组 (act_id=" + escHtml(actId) + ")，请确认是否正确。");
            window._pendingActIds.shift();
            continue;
        }

        // Step 2: 逐个 lottery group 取回
        var actSuccess = 0;
        var newCollectionsForAct = [];

        for (var li = 0; li < allParams.length; li++) {
            var p = allParams[li];
            var subProgress = progressBase + (li / allParams.length) * (85 / totalSteps);
            setProgress(Math.round(subProgress), "正在获取 act_id=" + p.act_id + " lottery_id=" + p.lottery_id + " (" + (doneSoFar + 1) + "/" + totalSteps + ")…");

            try {
                var fetchJson = await fetchCollection(p.act_id, p.lottery_id);
                if (fetchJson.code !== 0) {
                    addAlert("alert-err", "❌ 收藏集获取失败 (act_id=" + escHtml(p.act_id) + "): " + escHtml(String(fetchJson.message || fetchJson.code)));
                } else {
                    var result = parseData(fetchJson.data || {}, opts);
                    result.actId = p.act_id;
                    window._allCollections.push(result);
                    newCollectionsForAct.push(result);
                    actSuccess++;
                }
            } catch (err) {
                addAlert("alert-err", "❌ 获取失败 (act_id=" + escHtml(p.act_id) + "): " + escHtml(err.message || String(err)));
            }
        }

        // 从 pending 中移除当前 act_id
        window._pendingActIds.shift();
        pageFetchedCount++;

        if (actSuccess > 0) {
            state.successActIds++;
            if (!window._succeededActIds) window._succeededActIds = new Set();
            window._succeededActIds.add(actId);
        }

        // ── 立即显示刚加载的收藏集 ──
        if (newCollectionsForAct.length > 0) {
            var container = document.getElementById("results-body");
            // 如果是当前页第一次显示，先清空容器
            if (curPage.collections.length === 0 && pageFetchedCount === 1) {
                container.innerHTML = "";
                state.allLinks = [];
            }

            for (var nci = 0; nci < newCollectionsForAct.length; nci++) {
                var newColl = newCollectionsForAct[nci];
                curPage.collections.push(newColl);
                curPage.cardCount += newColl.cards.length;
                appendSingleBlock(container, newColl);
            }
            // 更新紧凑进度条
            updateLoadProgress();

            updateActionButtons();
        }

        // ── 判断是否达到分页阈值 ──
        // 当前收藏集已完整加载完毕，现在判断总卡牌是否 ≥ 200
        if (curPage.cardCount >= PAGE_CARD_LIMIT && window._pendingActIds.length > 0) {
            // 达到了阈值且还有剩余 act_id → 停在此页，显示分页
            addAlert("alert-info", "📄 第 " + (getTotalPages()) + " 页已达 " + curPage.cardCount + " 张，剩余 " + window._pendingActIds.length + " 个待加载");
            break;
        }
    }

    // 调整计数
    state.failActIds = state.totalActIds - state.successActIds;
    if (state.failActIds < 0) state.failActIds = 0;

    // 汇总信息
    var totalCollections = window._allCollections.length;
    var summaryParts2 = [];
    if (window._batchSkippedCount > 0) {
        summaryParts2.push("跳过 " + window._batchSkippedCount + " 个（已存在）");
    }
    summaryParts2.push("本次查询 " + state.totalActIds + " 个 act_id");
    summaryParts2.push("成功 " + state.successActIds + " 个");
    if (state.failActIds > 0) summaryParts2.push("失败 " + state.failActIds + " 个");
    summaryParts2.push("累计共 " + totalCollections + " 个收藏集");
    addAlert(state.failActIds > 0 ? "alert-warn" : "alert-ok", summaryParts2.join("，"));

    // 更新进度
    setProgress(100, "完成");
    setTimeout(hideProgress, 900);

    window._isPageFetching = false;
    btn.disabled = false;

    // 如果还有待加载，新建下一页
    if (window._pendingActIds.length > 0) {
        window._pages.push({ collections: [], cardCount: 0 });
    }

    // 显示/隐藏下载全部按钮
    if (state.allLinks.length > 0) {
        document.getElementById("btn-dl-all").style.display = "inline-flex";
        document.getElementById("dl-type-chks").style.display = "flex";
        document.getElementById("dl-chk-img").checked =
            document.getElementById("opt-img").checked;
        document.getElementById("dl-chk-vid").checked =
            document.getElementById("opt-vid").checked;
        document.getElementById("dl-chk-wm").checked =
            document.getElementById("opt-wm").checked;
    } else {
        document.getElementById("dl-type-chks").style.display = "none";
    }

    updatePaginationUI();
}

/* ============================================================
   Download all (open links sequentially)
   ============================================================ */
// 批量下载所有资源（图片/视频）
async function downloadAll() {
    const btn = document.getElementById("btn-dl-all");

    try {
        const btn = document.getElementById("btn-dl-all");

        btn.disabled = true;

        setZipProgress("准备下载...");
        if (!state.allLinks.length) {
            return;
        }

        const chkImg = document.getElementById("dl-chk-img").checked;
        const chkVid = document.getElementById("dl-chk-vid").checked;
        const chkWm = document.getElementById("dl-chk-wm").checked;

        const typeMap = {
            "dl-a-img": chkImg,
            "dl-a-vid": chkVid,
            "dl-a-wm": chkWm,
        };

        // =========================
        // URL 去重
        // =========================

        const seen = new Set();

        const links = state.allLinks.filter((link) => {
            if (!typeMap[link.type]) {
                return false;
            }

            let normalizedUrl = link.url;

            if (
                link.type === 'dl-a-vid' ||
                link.type === 'dl-a-wm'
            ) {
                normalizedUrl = link.url.split('?')[0];
            }

            const key =
                (link.collectionFolder || "未知合集") +
                "|" +
                link.type +
                "|" +
                normalizedUrl;

            if (seen.has(key)) {
                return false;
            }

            seen.add(key);

            return true;
        });

        if (!links.length) {
            alert("请至少选择一种资源类型");
            return;
        }

        // =========================
        // ZIP 路径（多合集分大文件夹，内部按类型分类）
        // =========================
        const typeFolderMap = {
            "dl-a-img": "img",
            "dl-a-vid": "video",
            "dl-a-wm": "watermark_video",
        };

        function withSuffix(filename, index) {
            const dotIndex = filename.lastIndexOf(".");
            if (dotIndex > 0) {
                const name = filename.slice(0, dotIndex);
                const ext = filename.slice(dotIndex);
                return `${name}(${index})${ext}`;
            }
            return `${filename}(${index})`;
        }

        const hasMultipleCollections =
            Array.isArray(window._allCollections) &&
            window._allCollections.length > 1;

        const usedZipPaths = new Set();
        for (const link of links) {
            const baseParts = [];
            if (hasMultipleCollections) {
                baseParts.push(link.collectionFolder || "未知合集");
            }
            baseParts.push(typeFolderMap[link.type] || "other");

            let index = 0;
            let fileName = link.filename;
            let zipPath = `${baseParts.join("/")}/${fileName}`;
            while (usedZipPaths.has(zipPath)) {
                index += 1;
                fileName = withSuffix(link.filename, index);
                zipPath = `${baseParts.join("/")}/${fileName}`;
            }
            usedZipPaths.add(zipPath);
            link.zipPath = zipPath;
        }

        // 应用模式下优先走后端按目录落盘
        if (isAppMode()) {
            try {
                let savedCount = 0;
                let failedCount = 0;
                let duplicateCount = 0;
                let rootDir = "";

                for (let i = 0; i < links.length; i++) {
                    const link = links[i];
                    setZipProgress(`正在保存 ${i + 1}/${links.length}：${link.filename}`);

                    try {
                        const resp = await fetch(`${API_BASE}/api/save_file`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ item: link }),
                        });
                        const j = await resp.json();

                        if (j && j.code === 0) {
                            savedCount += 1;
                            if (j.duplicate) {
                                duplicateCount += 1;
                            }
                            if (j.root_dir) {
                                rootDir = j.root_dir;
                            }
                        } else {
                            failedCount += 1;
                            console.error("保存单文件失败:", j, link);
                        }
                    } catch (err) {
                        failedCount += 1;
                        console.error("保存单文件异常:", err, link);
                    }
                }

                if (savedCount > 0) {
                    if (failedCount > 0) {
                        setZipProgress(
                            `已保存 ${savedCount}/${links.length}，去重 ${duplicateCount}，失败 ${failedCount}，目录：${rootDir || "downloads"}`,
                        );
                    } else {
                        setZipProgress(`已保存 ${savedCount}/${links.length}，去重 ${duplicateCount}，目录：${rootDir || "downloads"}`);
                    }
                    return;
                }

                console.error("应用模式保存失败: 无文件保存成功");
                setZipProgress("应用目录保存失败，改为打包 ZIP...");
            } catch (err) {
                console.error("应用模式保存异常:", err);
                setZipProgress("应用目录保存失败，改为打包 ZIP...");
            }
        }

        // =========================
        // 创建 ZIP
        // =========================

        const zip = new JSZip();

        let done = 0;

        const CONCURRENT = 5;

        let index = 0;

        async function worker() {
            while (true) {
                const current = index++;

                if (current >= links.length) {
                    return;
                }

                const link = links[current];

                try {
                    setZipProgress(
                        `正在下载 ${done}/${links.length}：${link.filename}`,
                    );
                    let fetchUrl = link.url;

                    // 图片走代理
                    if (link.type === "dl-a-img") {
                        fetchUrl = `${API_BASE}/api/proxy_img?url=${encodeURIComponent(link.url)}`;
                    }

                    const resp = await fetch(fetchUrl);

                    if (!resp.ok) {
                        throw new Error(`HTTP ${resp.status}`);
                    }

                    const blob = await resp.blob();

                    zip.file(link.zipPath || link.filename, blob);

                    done++;

                    console.log(`已添加 ${done}/${links.length}: ${link.filename}`);
                } catch (err) {
                    console.error("下载失败:", link.filename, err);
                }
            }
        }

        // 并发下载
        await Promise.all(Array.from({ length: CONCURRENT }, () => worker()));

        // =========================
        // 生成 ZIP
        // =========================

        setZipProgress("正在生成压缩包...");

        const zipBlob = await zip.generateAsync(
            {
                type: "blob",
                compression: 'STORE', // 不压缩，直接打包，提升生成速度
            },
            (metadata) => {
                setZipProgress(`正在生成压缩包：${metadata.percent.toFixed(1)}%`);
            },
        );

        // =========================
        // ZIP 名字
        // =========================

        const typeNames = [];

        if (chkImg) {
            typeNames.push("图片");
        }

        if (chkVid) {
            typeNames.push("视频");
        }

        if (chkWm) {
            typeNames.push("水印视频");
        }

        const typeSuffix =
            typeNames.length === 3 ? "全部" : typeNames.join("+");

        let zipName = "B站收藏集";

        if (window._allCollections && window._allCollections.length === 1) {
            zipName = window._allCollections[0].name || zipName;
        } else if (
            window._allCollections &&
            window._allCollections.length > 1
        ) {
            zipName = `B站收藏集_${window._allCollections.length}个合集`;
        }

        const safeZipName = zipName.replace(/[<>:"/\\|?*]/g, "_").trim();

        const finalZipName = `${safeZipName}_${typeSuffix}.zip`;
        saveAs(zipBlob, finalZipName);

        setZipProgress("下载完成（ZIP）");

        btn.disabled = false;
    } finally {
        btn.disabled = false;
    }
}

/* ============================================================
   Clear all
   ============================================================ */
function clearAll() {
    document.getElementById("act-id-input").value = "";
    document.getElementById("qr-thumbs").innerHTML = "";
    document.getElementById("qr-input").value = "";
    document.getElementById("results-body").innerHTML = "";
    document.getElementById("alerts").innerHTML = "";
    document.getElementById("results-wrap").classList.remove("on");
    document.getElementById("btn-dl-all").style.display = "none";
    document.getElementById("pagination").style.display = "none";
    hideProgress();
    state.allLinks = [];
    state.totalActIds = 0;
    state.successActIds = 0;
    state.failActIds = 0;
    window._allCollections = [];
    window._queriedActIds = new Set();
    window._succeededActIds = new Set();
    window._pages = [{ collections: [], cardCount: 0 }];
    window._currentPageIdx = 0;
    window._pendingActIds = [];
    window._pendingOpts = null;
    window._isPageFetching = false;
    window._batchSkippedCount = 0;
    setZipProgress('');
    updateActionButtons();
}
function setZipProgress(text) {
    const el = document.getElementById("zip-progress-text");

    if (el) {
        el.textContent = text || "";
    }
}

/* ============================================================
   Share link
   ============================================================ */
function doShare() {
    var succeeded = window._succeededActIds;
    if (!succeeded || !succeeded.size) {
        showToast("❌ 没有查询成功的 act_id 可供分享", true);
        return;
    }

    var actIds = Array.from(succeeded);
    var url = location.origin + location.pathname + "?act_id=" + actIds.join(",");

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () {
            showToast("✅ 分享链接已复制到剪切板", false);
        }).catch(function () {
            showToast("❌ 复制失败", true);
        });
    } else {
        // Fallback for older browsers
        try {
            var ta = document.createElement("textarea");
            ta.value = url;
            ta.style.position = "fixed";
            ta.style.opacity = "0";
            document.body.appendChild(ta);
            ta.select();
            document.execCommand("copy");
            document.body.removeChild(ta);
            showToast("✅ 分享链接已复制到剪切板", false);
        } catch (e) {
            showToast("❌ 复制失败", true);
        }
    }
}
// 自动读取 URL 参数（兼容动态加载脚本场景）
function autoStartFromUrl() {
    var params = new URLSearchParams(window.location.search);
    var raw = params.get("id") || params.get("act_id");
    if (!raw || !raw.trim()) return;

    var actIds = parseActIds(raw);
    if (!actIds.length) {
        // Maybe a URL — defer to extractActId (async)
        extractActId(raw.trim()).then(function (single) {
            if (single) {
                var ids = parseActIds(single);
                if (ids.length) {
                    document.getElementById("act-id-input").value = ids.join(", ");
                    startFetch();
                }
            }
        });
    } else {
        document.getElementById("act-id-input").value = actIds.join(", ");
        startFetch();
    }
}

// DOMContentLoaded may have already fired (app.js is dynamically loaded)
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoStartFromUrl);
} else {
    autoStartFromUrl();
}

/* ============================================================
   Batch Scan: check a range of act_ids for existence
   — 顺序扫描 + 随机延迟，避免触发 B 站 412 风控
   ============================================================ */
let batchScanAbort = false;

/** 随机延迟 ms */
function randomDelay(min, max) {
    return new Promise(function (resolve) {
        setTimeout(resolve, min + Math.random() * (max - min));
    });
}

async function startBatchScan() {
    var startEl = document.getElementById("scan-start");
    var endEl = document.getElementById("scan-end");
    var btn = document.getElementById("btn-scan");
    var resultsEl = document.getElementById("scan-results");
    var progressEl = document.getElementById("scan-progress");
    var progBar = document.getElementById("scan-prog-bar");
    var progText = document.getElementById("scan-prog-text");
    var hintEl = document.getElementById("scan-hint");

    var start = parseInt(startEl.value, 10);
    var end = parseInt(endEl.value, 10);

    if (isNaN(start) || isNaN(end) || start < 1 || end < 1 || end < start) {
        hintEl.textContent = "⚠️ 请输入有效的 act_id 范围（起始 ≤ 结束，且均为正整数）。";
        hintEl.style.color = "#ff4d4f";
        return;
    }
    hintEl.style.color = "";
    hintEl.textContent = "正在扫描 " + start + " ~ " + end + "，共 " + (end - start + 1) + " 个 act_id…";

    batchScanAbort = false;
    btn.disabled = true;
    btn.textContent = "⏳ 扫描中…";
    btn.style.display = "none";
    document.getElementById("btn-scan-stop").style.display = "inline-flex";
    progressEl.style.display = "block";
    resultsEl.innerHTML = "";

    var ids = [];
    for (var i = start; i <= end; i++) {
        ids.push(i);
    }
    var total = ids.length;
    var found = [];
    var notFound = [];
    var errors = [];

    // ── 顺序扫描，每两个请求之间随机延迟 0.5~1.5 秒 ──
    for (var idx = 0; idx < total; idx++) {
        if (batchScanAbort) break;

        var actId = ids[idx];

        // 请求之间加随机延迟（第一个不等）
        if (idx > 0) {
            await randomDelay(500, 1500);
        }

        // 带指数退避的重试（最多 3 次）
        var success = false;
        for (var retry = 0; retry < 3 && !success; retry++) {
            if (batchScanAbort) break;
            if (retry > 0) {
                await randomDelay(2000 * retry, 2000 * retry + 1000);
            }
            try {
                var res = await fetch(
                    API_BASE + "/api/check_act_id?act_id=" + encodeURIComponent(actId)
                );
                var json = await res.json();
                if (json.code === 0 && json.data) {
                    if (json.data.exists) {
                        found.push({ act_id: actId, name: json.data.name });
                    } else {
                        notFound.push(actId);
                    }
                    success = true;
                } else if (res.status >= 500) {
                    // 服务端错误，可以重试
                    continue;
                } else {
                    errors.push(actId);
                    success = true; // 标记为已处理
                }
            } catch (err) {
                if (err.name === "AbortError") { batchScanAbort = true; break; }
                // 网络错误可能是 412，重试
                continue;
            }
        }
        if (!success) {
            errors.push(actId);
        }

        // 更新进度
        var pct = Math.round(((idx + 1) / total) * 100);
        progBar.style.width = pct + "%";
        progText.textContent = "已检查 " + (idx + 1) + "/" + total +
            "，存在 " + found.length + " 个，不存在 " + notFound.length + " 个" +
            (errors.length ? "，错误 " + errors.length + " 个" : "");

        // 每 10 个或最后更新一次界面
        if ((idx + 1) % 10 === 0 || idx + 1 === total) {
            renderScanResults(resultsEl, found, notFound, errors, total);
        }
    }

    // Final render
    renderScanResults(resultsEl, found, notFound, errors, total);

    btn.disabled = false;
    btn.textContent = "🚀 开始扫描";
    btn.style.display = "";
    document.getElementById("btn-scan-stop").style.display = "none";
    hintEl.textContent = "扫描完成！共 " + total + " 个 act_id，存在 " + found.length + " 个。点击绿色标签可填入输入框并查询。";

    // If some act_ids exist, offer to query them
    if (found.length > 0) {
        var actIdList = found.map(function (f) { return f.act_id; }).join(", ");
        var fillBtn = document.createElement("div");
        fillBtn.style.cssText = "margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;";
        fillBtn.innerHTML =
            '<button class="btn btn-primary" onclick="fillFoundActIds()" style="font-size:12px;padding:5px 14px;">📋 查询找到的 ' + found.length + ' 个 act_id</button>' +
            '<span style="font-size:11px;color:var(--sub);">将已找到的 act_id 填入输入框并获取下载链接</span>';
        resultsEl.appendChild(fillBtn);
        // Store found ids for fillFoundActIds
        window._batchFoundIds = found.map(function (f) { return f.act_id; });
    }
}

function stopBatchScan() {
    batchScanAbort = true;
    var btn = document.getElementById("btn-scan");
    var stopBtn = document.getElementById("btn-scan-stop");
    var hintEl = document.getElementById("scan-hint");
    btn.disabled = false;
    btn.textContent = "🚀 开始扫描";
    btn.style.display = "";
    stopBtn.style.display = "none";
    hintEl.textContent = "⏹ 已手动停止扫描。";
}

function renderScanResults(container, found, notFound, errors, total) {
    container.innerHTML = "";

    // Stats
    var stats = document.createElement("div");
    stats.className = "scan-stats";
    stats.innerHTML =
        '<span class="scan-stat-item scan-stat-total">📊 总计 <span class="scan-stat-num">' + total + '</span></span>' +
        '<span class="scan-stat-item scan-stat-ok">✅ 存在 <span class="scan-stat-num">' + found.length + '</span></span>' +
        '<span class="scan-stat-item scan-stat-fail">❌ 不存在 <span class="scan-stat-num">' + notFound.length + '</span></span>' +
        (errors.length ? '<span class="scan-stat-item" style="color:#fa8c16;">⚠️ 错误 <span class="scan-stat-num" style="color:#fa8c16;">' + errors.length + '</span></span>' : "");
    container.appendChild(stats);

    // Only show badges if total is reasonable
    if (total > 500) {
        // Too many to show individually, show summary only
        return;
    }

    // Found badges (green)
    found.sort(function (a, b) { return a.act_id - b.act_id; });
    for (var i = 0; i < found.length; i++) {
        var f = found[i];
        var badge = document.createElement("span");
        badge.className = "scan-badge scan-badge-ok act-id-clickable";
        badge.title = f.name || ("act_id=" + f.act_id);
        badge.textContent = f.act_id;
        badge.onclick = (function (id, name) {
            return function () {
                var input = document.getElementById("act-id-input");
                var existing = input.value.trim();
                var ids = existing ? parseActIds(existing) : [];
                if (ids.indexOf(String(id)) === -1) {
                    ids.push(String(id));
                }
                input.value = ids.join(", ");
                input.focus();
                showToast("✅ 已添加 act_id=" + id + (name ? "（" + name + "）" : ""), false);
            };
        })(f.act_id, f.name);
        container.appendChild(badge);
    }

    // Separator if both found and not found
    if (found.length > 0 && notFound.length > 0) {
        var sep = document.createElement("span");
        sep.style.cssText = "font-size:10px;color:#ccc;padding:0 2px;";
        sep.textContent = "|";
        container.appendChild(sep);
    }

    // Not found badges (red) - only show first 50 if too many
    notFound.sort(function (a, b) { return a - b; });
    var showNotFound = notFound.slice(0, 50);
    for (var j = 0; j < showNotFound.length; j++) {
        var badge2 = document.createElement("span");
        badge2.className = "scan-badge scan-badge-fail";
        badge2.textContent = showNotFound[j];
        container.appendChild(badge2);
    }
    if (notFound.length > 50) {
        var more = document.createElement("span");
        more.className = "scan-badge scan-badge-skip";
        more.textContent = "…还有 " + (notFound.length - 50) + " 个";
        container.appendChild(more);
    }
}

function fillFoundActIds() {
    var ids = window._batchFoundIds;
    if (!ids || !ids.length) return;
    document.getElementById("act-id-input").value = ids.join(", ");
    showToast("✅ 已填入 " + ids.length + " 个 act_id", false);
    startFetch();
}

// ── 回到顶部 ──
window.addEventListener("scroll", function () {
    var el = document.getElementById("back-top");
    if (!el) return;
    if (window.scrollY > 400) {
        el.classList.add("show");
    } else {
        el.classList.remove("show");
    }
});
