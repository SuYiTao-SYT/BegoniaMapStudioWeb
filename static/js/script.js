async function renderMap() {
    const svgFile = document.getElementById('svgFile').files[0];
    const csvFile = document.getElementById('csvFile').files[0];
    const mapTitle = document.getElementById('mapTitle').value;
    const strokeWidth = document.getElementById('strokeWidth').value;
    const btn = document.getElementById('renderBtn');
    const container = document.getElementById('svgContainer');

    if (!svgFile || !csvFile) {
        alert("请先选择 SVG 和 CSV 文件！");
        return;
    }

    const formData = new FormData();
    formData.append('svg_file', svgFile);
    formData.append('csv_file', csvFile);
    formData.append('map_title', mapTitle);
    formData.append('stroke_width', strokeWidth);

    btn.textContent = "⏳ 处理中...";
    btn.disabled = true;
    container.innerHTML = '<div class="placeholder">正在渲染，请稍候...</div>'; //以此提示用户

    try {
        const response = await fetch('/api/process', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        console.log("服务器返回状态:", response.status); // 调试信息
        console.log("数据预览:", result); // 调试信息

        if (response.ok) {
            // 1. 注入 SVG
            container.innerHTML = result.svg_content;
            
            // 2. 显示下载按钮
            document.getElementById('downloadArea').style.display = 'block';
            document.getElementById('downloadLink').href = result.download_url;
            
            // 3. 绑定交互事件
            attachInteractiveEvents();
            
            console.log("SVG 已注入页面");
        } else {
            container.innerHTML = `<div class="placeholder" style="color:red">渲染出错: ${result.error}</div>`;
            alert("错误: " + result.error);
        }
    } catch (error) {
        console.error(error);
        container.innerHTML = `<div class="placeholder" style="color:red">网络请求失败</div>`;
        alert("网络请求失败，请检查控制台(F12)");
    } finally {
        btn.textContent = "🚀 生成地图";
        btn.disabled = false;
    }
}

// === 核心交互逻辑 ===
function attachInteractiveEvents() {
    const tooltip = document.getElementById('tooltip');
    // 找到所有带有 data-party 属性的路径 (我们在 renderer.py 里埋进去的)
    const districts = document.querySelectorAll('path[data-party]');

    districts.forEach(path => {
        // 鼠标移入
        path.addEventListener('mousemove', (e) => {
            const party = path.getAttribute('data-party');
            const rate = path.getAttribute('data-rate');
            const id = path.id; // 选区编号

            // 设置 tooltip 内容 (HTML)
            tooltip.innerHTML = `
                <div style="font-weight:bold; margin-bottom:2px;">${id}</div>
                <div>胜出: <span style="color:#ffcc00">${party}</span></div>
                <div>得票: ${rate}</div>
            `;
            
            // 设置位置 (跟随鼠标)
            tooltip.style.display = 'block';
            tooltip.style.left = (e.pageX + 15) + 'px';
            tooltip.style.top = (e.pageY + 15) + 'px';
        });

        // 鼠标移出
        path.addEventListener('mouseleave', () => {
            tooltip.style.display = 'none';
        });
    });
}