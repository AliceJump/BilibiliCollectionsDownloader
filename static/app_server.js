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
                    document.getElementById("act-id-input").value = actId;
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

    // Process redeem items in collect_list (emoji packages, etc.)
    function processRedeemResources(redeem) {
        if (!redeem || !redeem._suit_resources) return;
        var resources = redeem._suit_resources;
        if (!Array.isArray(resources)) return;
        resources.forEach(function (res) {
            if (!res || res.type !== "emoji") return;
            var cn = res.name || "表情";
            if (!map.has(cn)) map.set(cn, { card_name: cn, links: [] });
            var entry = map.get(cn);
            var images = res.images || {};
            if (opts.img && images.static) {
                entry.links.push({
                    url: images.static,
                    label: "😊",
                    cls: "dl-a-emoji",
                    ext: "png",
                });
            }
            if (opts.img && images.gif) {
                entry.links.push({
                    url: images.gif,
                    label: "😊",
                    cls: "dl-a-emoji",
                    ext: "gif",
                });
            }
            if (opts.img && images.webp) {
                entry.links.push({
                    url: images.webp,
                    label: "😊",
                    cls: "dl-a-emoji",
                    ext: "webp",
                });
            }
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
                processRedeemResources(c);
            });
        } else if (typeof cl === "object") {
            (cl.collect_infos || []).forEach(function (c) {
                if (c && c.card_item && c.card_item.card_type_info)
                    processCardTypeInfo(c.card_item.card_type_info);
                processRedeemResources(c);
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
                if (dl.cls === "dl-a-emoji" && !types.includes("emoji"))
                    types.push("emoji");
            }
            // tab标签
            const tabNames = { img: "🖼️", vid: "🎬", wm: "💧", emoji: "😊" };
            let activeType = types[0] || "img";
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
                    } else if (activeType === "emoji" && dl.cls === "dl-a-emoji") {
                        const img = document.createElement("img");
                        img.src = `${API_BASE}/api/proxy_img?url=${encodeURIComponent(dl.url)}`;
                        img.alt = "表情预览";
                        img.loading = "lazy";
                        img.referrerPolicy = "no-referrer";
                        preview.appendChild(img);
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
        block.appendChild(header);
        block.appendChild(body);

        // ── 点击切换折叠 ──
        header.addEventListener("click", function () {
            var isClosed = body.classList.toggle("closed");
            toggle.classList.toggle("collapsed", isClosed);
            header.classList.toggle("collapsed", isClosed);
            header.setAttribute("aria-expanded", !isClosed);
        });

        container.appendChild(block);
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
   Main: start fetch (supports multiple act_ids)
   ============================================================ */
async function startFetch() {
    var raw = document.getElementById("act-id-input").value.trim();
    if (!raw) {
        clearAlerts();
        document.getElementById("results-wrap").classList.add("on");
        addAlert("alert-warn", "⚠️ 请输入至少一个 act_id（纯数字），多个用英文逗号分隔。");
        return;
    }

    // Try direct parsing first (comma-separated pure numbers)
    var actIds = parseActIds(raw);
    // If no direct numbers, try extractActId (handles URLs, short links, single act_id)
    if (!actIds.length) {
        var single = await extractActId(raw);
        if (single) {
            actIds = parseActIds(single);
        }
    }

    if (!actIds.length) {
        clearAlerts();
        document.getElementById("results-wrap").classList.add("on");
        addAlert("alert-warn", "⚠️ 请输入有效的 <code>act_id</code>（纯数字）、含 <code>act_id</code> 参数的完整链接，或 b23.tv 短链接。支持多个用英文逗号分隔。");
        return;
    }

    // ---- 去重：过滤已查询过的 act_id ----
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

    var skippedCount = actIds.length - newActIds.length;

    var opts = {
        img: document.getElementById("opt-img").checked,
        vid: document.getElementById("opt-vid").checked,
        wm: document.getElementById("opt-wm").checked,
    };

    var btn = document.getElementById("btn-start");
    btn.disabled = true;
    showProgress();
    document.getElementById("results-wrap").classList.add("on");
    clearAlerts();
    document.getElementById("results-body").innerHTML = "";
    document.getElementById("btn-dl-all").style.display = "none";

    // ---- 累计：不清空已有集合 ----
    if (!window._allCollections) window._allCollections = [];
    var collections = window._allCollections;
    var prevCount = collections.length;

    // Reset per-batch stats
    state.totalActIds = newActIds.length;
    state.successActIds = 0;
    state.failActIds = 0;

    var totalSteps = newActIds.length;

    setProgress(5, "准备查询 " + totalSteps + " 个 act_id…");

    // Process each act_id sequentially
    for (var ai = 0; ai < newActIds.length; ai++) {
        var actId = newActIds[ai];
        var progressBase = 5 + (ai / totalSteps) * 85;

        // Step 1: get lottery params for this act_id
        setProgress(progressBase, "正在查询分组：act_id=" + actId + " (" + (ai + 1) + "/" + totalSteps + ")…");
        var allParams;
        try {
            var paramsRes = await fetch(API_BASE + "/api/get_params?act_id=" + encodeURIComponent(actId));
            var paramsJson = await paramsRes.json();
            if (paramsJson.code !== 0) {
                state.failActIds++;
                addAlert("alert-err", "❌ 分组查询失败 (act_id=" + escHtml(actId) + "): " + escHtml(String(paramsJson.message || paramsJson.code)));
                continue;
            }
            allParams = paramsJson.data || [];
        } catch (err) {
            state.failActIds++;
            addAlert("alert-err", "❌ 分组查询失败 (act_id=" + escHtml(actId) + "): " + escHtml(err.message || String(err)));
            continue;
        }

        if (!allParams.length) {
            state.failActIds++;
            addAlert("alert-warn", "⚠️ 未找到收藏集分组 (act_id=" + escHtml(actId) + ")，请确认是否正确。");
            continue;
        }

        // Step 2: fetch collections for each lottery group
        var actSuccess = 0;
        for (var li = 0; li < allParams.length; li++) {
            var p = allParams[li];
            var subProgress = progressBase + (li / allParams.length) * (85 / totalSteps);
            setProgress(Math.round(subProgress), "正在获取 act_id=" + p.act_id + " lottery_id=" + p.lottery_id + " (" + (ai + 1) + "/" + totalSteps + ")…");

            try {
                var fetchJson = await fetchCollection(p.act_id, p.lottery_id);
                if (fetchJson.code !== 0) {
                    addAlert("alert-err", "❌ 收藏集获取失败 (act_id=" + escHtml(p.act_id) + "): " + escHtml(String(fetchJson.message || fetchJson.code)));
                } else {
                    var result = parseData(fetchJson.data || {}, opts);
                    result.actId = p.act_id;
                    collections.push(result);
                    actSuccess++;
                    addAlert("alert-ok", "✅ " + escHtml(result.name) + " — " + result.cards.length + " 个卡牌 (act_id=" + escHtml(p.act_id) + ")");
                }
            } catch (err) {
                addAlert("alert-err", "❌ 获取失败 (act_id=" + escHtml(p.act_id) + "): " + escHtml(err.message || String(err)));
            }
        }
        if (actSuccess > 0) {
            state.successActIds++;
            if (!window._succeededActIds) window._succeededActIds = new Set();
            window._succeededActIds.add(actId);
        } else if (state.failActIds === 0 || state.failActIds < totalSteps) {
            // If at least one lottery group was attempted but all failed
            // (the fail counter was already incremented for get_params failures; for collection failures, we check actSuccess)
            // Don't double-count — only mark fail if no success at all
        }
    }

    // Adjust fail count
    state.failActIds = state.totalActIds - state.successActIds;
    if (state.failActIds < 0) state.failActIds = 0;

    // Show summary before results
    var summaryParts = [];
    if (skippedCount > 0) {
        summaryParts.push("跳过 " + skippedCount + " 个（已存在）");
    }
    summaryParts.push("本次查询 " + state.totalActIds + " 个 act_id，成功 " + state.successActIds + " 个");
    if (state.failActIds > 0) {
        summaryParts.push("失败 " + state.failActIds + " 个");
    }
    summaryParts.push("累计共 " + collections.length + " 个收藏集");
    var summaryMsg = summaryParts.join("，");
    addAlert(state.failActIds > 0 ? "alert-warn" : "alert-ok", summaryMsg);

    setProgress(100, "完成");
    setTimeout(hideProgress, 900);
    renderResults(collections);
    btn.disabled = false;
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
    hideProgress();
    state.allLinks = [];
    state.totalActIds = 0;
    state.successActIds = 0;
    state.failActIds = 0;
    window._allCollections = [];
    window._queriedActIds = new Set();
    window._succeededActIds = new Set();
    setZipProgress('');
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
    var raw = document.getElementById("act-id-input").value.trim();
    var actIds = parseActIds(raw);

    if (!actIds.length) {
        showToast("❌ 请先输入至少一个 act_id", true);
        return;
    }

    // 只保留查询成功的 act_id
    var succeeded = window._succeededActIds;
    if (succeeded && succeeded.size > 0) {
        actIds = actIds.filter(function (id) { return succeeded.has(id); });
    }

    if (!actIds.length) {
        showToast("❌ 没有查询成功的 act_id 可供分享", true);
        return;
    }

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
