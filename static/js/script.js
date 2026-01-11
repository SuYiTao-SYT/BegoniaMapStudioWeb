// 全局变量
let currentEditingId = null;
let selectedDistricts = new Set();
let globalPartyList = [];
let isBatchMode = false;
// === 缩放相关变量 ===
let currentScale = 1;
let currentTranslateX = 0;
let currentTranslateY = 0;
let isDragging = false;
let startDragX = 0;
let startDragY = 0;

// === 1. 渲染地图主函数 ===
async function renderMap(preserveZoom = false) {
    const svgInput = document.getElementById('svgFile');
    const csvInput = document.getElementById('csvFile');
    const mapTitle = document.getElementById('mapTitle').value;
    const strokeWidth = document.getElementById('strokeWidth').value;
    const btn = document.getElementById('renderBtn');
    const container = document.getElementById('svgContainer');

    const hasSvgRendered = container.innerHTML.includes('<svg');
    
    // 如果不是静默更新(比如点击保存时)，则检查文件
    if (!preserveZoom) {
        if (!svgInput.files[0] && !hasSvgRendered) {
            alert("请先上传 SVG 文件！");
            return;
        }
    }

    const formData = new FormData();
    if (svgInput.files[0]) formData.append('svg_file', svgInput.files[0]);
    if (csvInput.files[0]) formData.append('csv_file', csvInput.files[0]);
    
    formData.append('map_title', mapTitle);
    formData.append('stroke_width', strokeWidth);

    // 只有在非静默更新时才显示Loading，避免保存时闪烁
    if (!preserveZoom) {
        btn.textContent = "⏳ 处理中...";
        btn.disabled = true;
        if (!hasSvgRendered) {
            container.innerHTML = '<div class="placeholder">正在渲染，请稍候...</div>';
        }
    }

    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            container.innerHTML = result.svg_content;
            document.getElementById('downloadArea').style.display = 'block';
            document.getElementById('downloadLink').href = result.download_url;
            
            // 绑定交互事件
            attachInteractiveEvents();
            
            // 初始化缩放逻辑 (如果是保存更新，则不重置位置)
            if (!preserveZoom) {
                resetZoom(); // 新图，重置
            } else {
                applyTransform(); // 旧图更新，保持位置
            }
            if (currentViewMode === 'seats') {
                switchView('seats'); 
            }
            // 清空文件框
            svgInput.value = ''; 
            csvInput.value = ''; 

        } else {
            alert("错误: " + result.error);
        }
    } catch (error) {
        console.error(error);
        alert("网络请求失败");
    } finally {
        btn.textContent = "🚀 生成/更新地图";
        btn.disabled = false;
    }
}
// === 初始化高亮图层 ===
// 这个函数需要在 renderMap 成功后调用一次
function initHighlightLayer() {
    const svg = document.querySelector('#svgContainer svg');
    if (!svg) return;
    
    // 检查是否已经有高亮层
    let layer = document.getElementById('highlight-layer');
    if (!layer) {
        layer = document.createElementNS("http://www.w3.org/2000/svg", "g");
        layer.id = 'highlight-layer';
        // 关键：设为 pointer-events: none，让鼠标能穿透替身点到底下的真身
        // 这样你依然可以拖拽、点击
        layer.style.pointerEvents = 'none'; 
        svg.appendChild(layer); // 放在最后，即最顶层
    }
}
// === 2. 缩放和平移逻辑 (新增) ===
function initZoomControls() {
    const viewport = document.getElementById('mapViewport');
    
    // === 滚轮缩放 (以鼠标为中心) ===
    viewport.addEventListener('wheel', (e) => {
        e.preventDefault();
        
        // 1. 获取鼠标相对于 mapViewport 的坐标
        const rect = viewport.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // 2. 决定缩放方向和力度
        // 这里的 0.1 是基础步长，你可以根据手感调整
        // 也可以做成 multiplicative (乘法) 缩放，比如 scale * 1.1，那样更平滑
        const delta = e.deltaY > 0 ? -0.2 : 0.2; 
        
        // 3. 传入鼠标坐标
        zoomMap(delta, mouseX, mouseY);

    }, { passive: false });

    // 鼠标拖拽平移
    viewport.addEventListener('mousedown', (e) => {
        isDragging = true;
        startDragX = e.clientX - currentTranslateX;
        startDragY = e.clientY - currentTranslateY;
        viewport.style.cursor = 'grabbing';
    });

    // === 关键优化：使用 requestAnimationFrame 节流 ===
    let isTicking = false; // 锁

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        e.preventDefault();

        // 记录最新坐标，但不立即应用
        const nextX = e.clientX - startDragX;
        const nextY = e.clientY - startDragY;

        if (!isTicking) {
            window.requestAnimationFrame(() => {
                currentTranslateX = nextX;
                currentTranslateY = nextY;
                applyTransform();
                isTicking = false; // 解锁，允许下一帧更新
            });
            isTicking = true;
        }
    });

    window.addEventListener('mouseup', () => {
        isDragging = false;
        if (viewport) viewport.style.cursor = 'grab';
    });
}

// === 缩放核心逻辑 (修正版：配合 transform-origin: 0 0) ===
function zoomMap(amount, originX, originY) {
    let newScale = currentScale + amount;

    // 1. 限制缩放范围
    if (newScale < 0.2) newScale = 0.2;
    if (newScale > 10.0) newScale = 10.0; // 可以稍微放宽一点上限

    // 2. 获取视口尺寸
    const viewport = document.getElementById('mapViewport');
    const rect = viewport.getBoundingClientRect();

    // 3. 确定缩放中心 (锚点)
    // 如果是滚轮缩放，originX/Y 是鼠标相对于 viewport 的坐标
    // 如果是按钮缩放，则取屏幕中心
    if (originX === undefined || originY === undefined) {
        originX = rect.width / 2;
        originY = rect.height / 2;
    }

    // 4. 核心数学公式：保持鼠标下的点不动
    // 公式：
    // WorldX = (MouseX - TranslateX) / OldScale
    // NewTranslateX = MouseX - (WorldX * NewScale)
    
    // a. 计算鼠标指向的点在"地图内部"的坐标 (World Coordinate)
    const worldX = (originX - currentTranslateX) / currentScale;
    const worldY = (originY - currentTranslateY) / currentScale;

    // b. 反推新的位移，使得该点在缩放后依然位于 originX, originY
    currentTranslateX = originX - (worldX * newScale);
    currentTranslateY = originY - (worldY * newScale);

    // 5. 应用
    currentScale = newScale;
    applyTransform();
}

// === 重置缩放 (修正版：让地图居中) ===
function resetZoom() {
    currentScale = 1;
    
    // 简单的居中计算 (假设地图大概占视口的 90%)
    const viewport = document.getElementById('mapViewport');
    const container = document.getElementById('svgContainer');
    
    if (viewport && container) {
        const vRect = viewport.getBoundingClientRect();
        const cRect = container.getBoundingClientRect(); // 此时还没transform，获取的是原始尺寸
        
        // 简单的居中算法：(视口宽 - 内容宽) / 2
        // 注意：因为 transform-origin 是 0 0，我们需要手动把它推到中间
        // 这里只是一个估算，为了初次显示好看
        currentTranslateX = (vRect.width - cRect.width) / 2;
        currentTranslateY = 20; // 顶部留一点空隙
    } else {
        currentTranslateX = 0;
        currentTranslateY = 0;
    }
    
    applyTransform();
}

function applyTransform() {
    const container = document.getElementById('svgContainer');
    if (container) {
        container.style.transform = `translate(${currentTranslateX}px, ${currentTranslateY}px) scale(${currentScale})`;
    }
}

// === 3. 绑定交互事件 ===
function attachInteractiveEvents() {
    const tooltip = document.getElementById('tooltip');
    const districts = document.querySelectorAll('path[data-party]');

    // 【关键在这里！】每次地图渲染完，必须先初始化高亮层
    initHighlightLayer();

    console.log(`[调试] 绑定交互事件: 找到了 ${districts.length} 个选区`);

    // 重新初始化缩放逻辑 (防止缩放失效)
    if (typeof initZoomControls === 'function') {
        // 这里的逻辑有点冗余，但为了保险起见确保缩放器能抓到新的 viewport
        // 通常 initZoomControls 在 window.onload 跑一次就够了
    }

    districts.forEach(path => {
        // A. 悬浮显示信息
        path.addEventListener('mousemove', (e) => {
            const party = path.getAttribute('data-party');
            const rate = path.getAttribute('data-rate');
            const id = path.id;

            tooltip.innerHTML = `
                <div style="font-weight:bold; margin-bottom:2px;">${id}</div>
                <div>胜出: <span style="color:#ffcc00">${party}</span></div>
                <div>得票: ${rate}</div>
            `;
            tooltip.style.display = 'block';
            tooltip.style.left = (e.pageX + 15) + 'px';
            tooltip.style.top = (e.pageY + 15) + 'px';
        });

        path.addEventListener('mouseleave', () => {
            tooltip.style.display = 'none';
        });

        // B. 点击事件 (区分 Shift)
        path.addEventListener('click', async (e) => {
            if (isDragging) return; 
            e.stopPropagation(); 

            if (e.shiftKey) {
                // Shift + 点击 -> 多选/反选
                toggleSelection(path);
            } else {
                // 普通点击 -> 打开编辑器
                console.log(`[调试] 单击选区: ${path.id}`);
                openEditor(path.id);
            }
        });
    });
    
    // C. 点击空白处清空 (防止Shift误触)
    const container = document.getElementById('svgContainer');
    // 使用 onmouseup 避免多次绑定
    container.onmouseup = (e) => {
        // 没按Shift才清空
        if (!e.shiftKey) {
            clearSelection();
        }
    };
}
// === 多选逻辑 ===
function toggleSelection(pathElement) {
    const id = pathElement.id;
    const layer = document.getElementById('highlight-layer');
    
    if (selectedDistricts.has(id)) {
        // === 反选：移除替身 ===
        selectedDistricts.delete(id);
        
        // 找到对应的替身并删除
        // 替身的 ID 约定为 "highlight-原ID"
        const clone = document.getElementById(`highlight-${id}`);
        if (clone) layer.removeChild(clone);
        
        // 移除原元素的标记（仅用于逻辑判断，不负责样式）
        pathElement.classList.remove('selected-source');

    } else {
        // === 选中：创建替身 ===
        selectedDistricts.add(id);
        pathElement.classList.add('selected-source');
        
        // 创建 <use> 标签
        const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
        use.setAttributeNS("http://www.w3.org/1999/xlink", "xlink:href", `#${id}`);
        use.id = `highlight-${id}`;
        
        // 给替身加样式类
        use.classList.add('highlight-clone');
        
        layer.appendChild(use);
    }
    
    console.log(`当前选中了 ${selectedDistricts.size} 个选区`);
    
    renderBatchPanel();
}

// === 清空选择 ===
function clearSelection() {
    selectedDistricts.clear();
    const layer = document.getElementById('highlight-layer');
    if (layer) layer.innerHTML = ''; // 直接清空所有替身
    
    // 清除原元素的标记
    document.querySelectorAll('.selected-source').forEach(el => el.classList.remove('selected-source'));
    document.getElementById('editorPanel').classList.remove('open');
    console.log("已清空选择");
}
// === 4. 打开编辑器 ===
async function openEditor(id) {
    isBatchMode = false;
    
    // UI 切换
    document.getElementById('editorPanel').classList.add('open');
    document.getElementById('modeSingle').style.display = 'block';
    document.getElementById('modeBatch').style.display = 'none';
    document.getElementById('btnSaveCommon').textContent = "💾 保存并更新";

    currentEditingId = id;
    const panel = document.getElementById('editorPanel');
    const title = document.getElementById('panelTitle');
    const inputsContainer = document.getElementById('voteInputs');
    
    panel.classList.add('open');
    title.textContent = `加载中...`;
    
    try {
        const res = await fetch(`/api/district/${id}`);
        const json = await res.json();
        
        if (json.status === 'success') {
            const data = json.data;
            title.textContent = `编辑: ${id}`;
            
            // 填充席位 (不再处理 Type)
            document.getElementById('editSeats').value = (data.info.Seats !== undefined) ? data.info.Seats : 1;
            
            inputsContainer.innerHTML = ''; 

            let currentTotalVotes = 0;
            if (data.votes && Object.keys(data.votes).length > 0) {
                if (Array.isArray(data.votes)) {
                    currentTotalVotes = data.votes.reduce((sum, item) => sum + item.count, 0);
                } else {
                    currentTotalVotes = Object.values(data.votes).reduce((a, b) => a + b, 0);
                }
            } else {
                currentTotalVotes = 100000;
            }

            const controlBar = document.createElement('div');
            controlBar.className = 'control-bar';
            controlBar.innerHTML = `<label><input type="checkbox" id="lockTotal" checked> 🔒 锁定总票数</label>`;
            inputsContainer.appendChild(controlBar);

            let partyList = [];
            if (Array.isArray(data.votes)) {
                partyList = data.votes;
            } else {
                for (const [key, val] of Object.entries(data.votes)) {
                    partyList.push({ id: key, name: key, count: val });
                }
            }
            if (globalPartyList.length === 0 && partyList.length > 0) {
                globalPartyList = partyList.map(p => ({id: p.id, name: p.name}));
            }
            partyList.forEach(item => {
                const percent = currentTotalVotes > 0 ? ((item.count / currentTotalVotes) * 100).toFixed(1) : 0;
                
                const row = document.createElement('div');
                row.className = 'vote-row';
                row.innerHTML = `
                    <div class="row-top">
                        <div class="vote-name" title="${item.name}">${item.name}</div>
                        <input type="number" class="vote-input" data-party="${item.id}" value="${item.count}">
                    </div>
                    <div class="row-bottom">
                        <input type="range" class="vote-slider" min="0" max="100" step="0.1" value="${percent}" data-party="${item.id}">
                        <div class="vote-percent">${percent}%</div>
                    </div>
                `;
                inputsContainer.appendChild(row);
            });

            // 绑定联动
            const allInputs = inputsContainer.querySelectorAll('.vote-input');
            const allSliders = inputsContainer.querySelectorAll('.vote-slider');
            const lockCheckbox = document.getElementById('lockTotal');

            const refreshUI = (newTotal) => {
                if (newTotal <= 0) newTotal = 1;
                allInputs.forEach((inp, idx) => {
                    const val = parseInt(inp.value) || 0;
                    const p = (val / newTotal) * 100;
                    allSliders[idx].value = p;
                    inp.parentNode.nextElementSibling.querySelector('.vote-percent').textContent = p.toFixed(1) + '%';
                });
            };

            const distributeVotes = (triggerPartyId, newCount) => {
                let currentInputs = Array.from(allInputs);
                let otherInputs = currentInputs.filter(i => i.dataset.party !== triggerPartyId);
                
                if (!lockCheckbox.checked || otherInputs.length === 0) {
                    refreshUI(Array.from(allInputs).reduce((s,i)=>s+(parseInt(i.value)||0),0));
                    return;
                }

                let remainingVotes = currentTotalVotes - newCount;
                if (remainingVotes < 0) remainingVotes = 0;

                let currentOthersTotal = otherInputs.reduce((sum, i) => sum + (parseInt(i.value)||0), 0);
                
                otherInputs.forEach(inp => {
                    let oldVal = parseInt(inp.value) || 0;
                    let ratio = currentOthersTotal > 0 ? (oldVal / currentOthersTotal) : (1 / otherInputs.length);
                    inp.value = Math.round(remainingVotes * ratio);
                });

                refreshUI(currentTotalVotes);
            };

            allInputs.forEach(input => {
                input.addEventListener('input', (e) => distributeVotes(e.target.dataset.party, parseInt(e.target.value)||0));
            });

            allSliders.forEach(slider => {
                slider.addEventListener('input', (e) => {
                    const p = parseFloat(e.target.value);
                    const baseTotal = lockCheckbox.checked ? currentTotalVotes : Array.from(allInputs).reduce((s,i)=>s+(parseInt(i.value)||0),0);
                    const newVal = Math.round((p / 100) * baseTotal);
                    const relatedInput = inputsContainer.querySelector(`.vote-input[data-party="${e.target.dataset.party}"]`);
                    relatedInput.value = newVal;
                    distributeVotes(e.target.dataset.party, newVal);
                });
            });

        }
    } catch (e) {
        console.error(e);
        title.textContent = "加载错误";
    }
}
function handleSaveAction() {
    if (isBatchMode) {
        applyBatchSwing();
    } else {
        saveChanges();
    }
}
// === 5. 保存修改 (优化版：保持面板打开) ===
async function saveChanges() {
    if (!currentEditingId) return;
    
    const btn = document.querySelector('.btn-save');
    const originalText = btn.textContent;
    btn.textContent = "正在保存...";
    btn.disabled = true;

    // 1. 获取席位数据
    const seatsVal = document.getElementById('editSeats').value;

    // 2. 获取票数数据
    const inputs = document.querySelectorAll('.vote-input');
    const newVotes = {};
    inputs.forEach(input => {
        newVotes[input.dataset.party] = parseInt(input.value) || 0;
    });
    
    try {
        const res = await fetch('/api/district/update', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                district_id: currentEditingId,
                seats: seatsVal, // 发送席位数据
                votes: newVotes
            })
        });
        
        if (res.ok) {
            // 关键：传入 true 参数，表示"保持缩放状态，不要闪烁"
            await renderMap(true); 
            // 关键：不再调用 closePanel()
        } else {
            alert("保存失败");
        }
    } catch (e) {
        console.error(e);
        alert("网络请求失败");
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

function closePanel() {
    document.getElementById('editorPanel').classList.remove('open');
}
// === 视图切换逻辑 ===
let currentViewMode = 'result'; // 'result' 或 'seats'

function switchView(mode) {
    currentViewMode = mode;
    
    // 1. 更新按钮样式
    document.getElementById('btnViewResult').className = mode === 'result' ? 'active' : '';
    document.getElementById('btnViewSeats').className = mode === 'seats' ? 'active' : '';

    // 2. 遍历所有选区修改颜色
    const districts = document.querySelectorAll('path[data-party]');
    
    districts.forEach(path => {
        if (mode === 'result') {
            // A. 恢复选情颜色
            const orgColor = path.getAttribute('data-org-color');
            if (orgColor) {
                path.style.fill = orgColor;
            }
        } else {
            // B. 席位热力图模式
            const seats = parseInt(path.getAttribute('data-seats')) || 0;
            path.style.fill = getSeatHeatmapColor(seats);
        }
    });
}

// 辅助：生成席位热力图颜色 (金色系)
function getSeatHeatmapColor(seats) {
    if (seats === 0) return '#eeeeee'; // 无改选
    if (seats === 1) return '#FFECB3'; // 浅金 (1席)
    if (seats === 2) return '#FFC107'; // 亮金 (2席)
    if (seats === 3) return '#FF8F00'; // 橙金 (3席)
    if (seats >= 4)  return '#D84315'; // 深橙红 (多席大区)
    return '#eeeeee';
}
function renderBatchPanel() {
    isBatchMode = true;
    
    // UI 切换
    document.getElementById('editorPanel').classList.add('open');
    document.getElementById('panelTitle').textContent = `批量操作`;
    
    document.getElementById('modeSingle').style.display = 'none';
    document.getElementById('modeBatch').style.display = 'block';
    
    // 更新数据显示
    document.getElementById('batchCountDisplay').textContent = selectedDistricts.size;
    
    // 填充政党下拉框 (如果还没填过)
    const select = document.getElementById('batchPartySelect');
    if (select.options.length === 0 && globalPartyList.length > 0) {
        select.innerHTML = globalPartyList.map(p => 
            `<option value="${p.id}">${p.name}</option>`
        ).join('');
    }
    
    // 绑定滑条显示 (也可以放在 window.onload 里只绑一次)
    const slider = document.getElementById('batchSwingSlider');
    slider.oninput = (e) => {
        const val = e.target.value;
        const display = document.getElementById('swingValueDisplay');
        display.textContent = (val > 0 ? '+' : '') + val + '%';
        display.style.color = val > 0 ? '#d32f2f' : (val < 0 ? '#388e3c' : '#333');
    };
    
    // 修改按钮文字
    document.getElementById('btnSaveCommon').textContent = "⚡ 应用批量摇摆";
}
async function applyBatchSwing() {
    const partyId = document.getElementById('batchPartySelect').value;
    const percent = document.getElementById('batchSwingSlider').value;
    const lockTotal = document.getElementById('batchLockTotal').checked; // 获取 Checkbox 状态
    const districtIds = Array.from(selectedDistricts);
    
    if (parseFloat(percent) === 0) {
        alert("摇摆幅度为 0");
        return;
    }

    const btn = document.getElementById('btnSaveCommon');
    const oldText = btn.textContent;
    btn.textContent = "计算中...";
    btn.disabled = true;

    try {
        const res = await fetch('/api/batch/swing', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                district_ids: districtIds,
                party_id: partyId,
                percent: percent,
                lock_total: lockTotal // 发送给后端
            })
        });

        if (res.ok) {
            await renderMap(true); 
        } else {
            alert("更新失败");
        }
    } catch (e) {
        console.error(e);
        alert("网络错误");
    } finally {
        btn.textContent = oldText;
        btn.disabled = false;
    }
}
// 页面加载完成后初始化缩放控制器
window.onload = function() {
    // 1. 初始化缩放控制器
    initZoomControls();

    // 2. === 新增：绑定高性能模式开关 ===
    const speedToggle = document.getElementById('optimizeSpeedToggle');
    const svgContainer = document.getElementById('svgContainer');

    // 监听切换
    speedToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            svgContainer.classList.add('fast-mode');
            console.log("已开启高性能模式: optimizeSpeed");
        } else {
            svgContainer.classList.remove('fast-mode');
            console.log("已关闭高性能模式: geometricPrecision");
        }
    });

    // 默认行为：为了流畅体验，我们可以默认帮用户勾选上（可选）
    // speedToggle.checked = true;
    // svgContainer.classList.add('fast-mode');
};