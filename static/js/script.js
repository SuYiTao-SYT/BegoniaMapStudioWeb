// 全局变量
let currentEditingId = null;

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

// === 2. 缩放和平移逻辑 (新增) ===
function initZoomControls() {
    const viewport = document.getElementById('mapViewport');
    
    // 滚轮缩放
    viewport.addEventListener('wheel', (e) => {
        e.preventDefault();
        const delta = e.deltaY > 0 ? -0.1 : 0.1;
        zoomMap(delta);
    });

    // 鼠标拖拽平移
    viewport.addEventListener('mousedown', (e) => {
        isDragging = true;
        startDragX = e.clientX - currentTranslateX;
        startDragY = e.clientY - currentTranslateY;
        viewport.style.cursor = 'grabbing';
    });

    window.addEventListener('mousemove', (e) => {
        if (!isDragging) return;
        e.preventDefault();
        currentTranslateX = e.clientX - startDragX;
        currentTranslateY = e.clientY - startDragY;
        applyTransform();
    });

    window.addEventListener('mouseup', () => {
        isDragging = false;
        if (viewport) viewport.style.cursor = 'grab';
    });
}

function zoomMap(amount) {
    let newScale = currentScale + amount;
    // 限制缩放范围
    if (newScale < 0.2) newScale = 0.2;
    if (newScale > 5.0) newScale = 5.0;
    currentScale = newScale;
    applyTransform();
}

function resetZoom() {
    currentScale = 1;
    currentTranslateX = 0;
    currentTranslateY = 0;
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

    // 每次渲染后，重新初始化缩放监听器(其实只要监听一次viewport即可，为了保险起见在onload调用)
    // 注意：initZoomControls 应该只运行一次，我们放在文件最底部调用

    districts.forEach(path => {
        // A. 悬浮
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

        // B. 点击 (因为现在有拖拽，我们需要区分是"点击"还是"拖拽结束")
        // 简单处理：判断鼠标按下和抬起的时间差或位移，这里简单用 click 事件
        path.addEventListener('click', async (e) => {
            // 如果正在拖拽地图，不触发点击
            if (isDragging) return; 
            
            e.stopPropagation(); 
            openEditor(path.id);
        });
    });
}

// === 4. 打开编辑器 ===
async function openEditor(id) {
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

// 页面加载完成后初始化缩放控制器
window.onload = function() {
    initZoomControls();
};