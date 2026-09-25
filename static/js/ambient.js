/* Low contrast binary rain in the navigation rail and overview hero. Local only. */
(function () {
    const canvases = document.querySelectorAll('.ambient-binary');
    if (!canvases.length) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (reducedMotion.matches) return;

    const glyphWidth = 15;
    const glyphHeight = 18;
    const trailLength = 5;

    canvases.forEach(function (canvas) {
        const surface = canvas.parentElement;
        const context = canvas.getContext('2d', { alpha: true });
        if (!surface || !context) return;

        let columns = [];
        let lastFrame = 0;
        let frameHandle = null;

        function resizeCanvas() {
            const bounds = surface.getBoundingClientRect();
            const ratio = Math.min(window.devicePixelRatio || 1, 1.5);
            canvas.width = Math.max(1, Math.round(bounds.width * ratio));
            canvas.height = Math.max(1, Math.round(bounds.height * ratio));
            context.setTransform(ratio, 0, 0, ratio, 0, 0);
            columns = Array.from({ length: Math.ceil(bounds.width / glyphWidth) }, () => ({
                y: Math.random() * bounds.height,
                speed: 0.35 + Math.random() * 0.45,
            }));
        }

        function draw(timestamp) {
            frameHandle = null;
            if (document.hidden || reducedMotion.matches) return;
            if (timestamp - lastFrame < 75) {
                frameHandle = window.requestAnimationFrame(draw);
                return;
            }
            lastFrame = timestamp;
            const bounds = surface.getBoundingClientRect();
            context.clearRect(0, 0, bounds.width, bounds.height);
            context.font = '12px ui-monospace, Consolas, monospace';
            context.textAlign = 'center';

            columns.forEach((column, index) => {
                const x = index * glyphWidth + glyphWidth / 2;
                for (let trail = 0; trail < trailLength; trail += 1) {
                    const y = column.y - trail * glyphHeight;
                    if (y < 0 || y > bounds.height) continue;
                    context.globalAlpha = 0.08 + (1 - trail / trailLength) * 0.22;
                    context.fillStyle = trail === 0 ? '#55e3b0' : '#20bd88';
                    context.fillText(Math.random() < 0.5 ? '0' : '1', x, y);
                }
                column.y += column.speed * glyphHeight;
                if (column.y - trailLength * glyphHeight > bounds.height) {
                    column.y = -Math.random() * bounds.height * 0.35;
                    column.speed = 0.35 + Math.random() * 0.45;
                }
            });
            context.globalAlpha = 1;
            frameHandle = window.requestAnimationFrame(draw);
        }

        function start() {
            if (!document.hidden && !reducedMotion.matches && frameHandle === null) {
                frameHandle = window.requestAnimationFrame(draw);
            }
        }

        function stop() {
            if (frameHandle !== null) window.cancelAnimationFrame(frameHandle);
            frameHandle = null;
        }

        resizeCanvas();
        start();
        window.addEventListener('resize', resizeCanvas, { passive: true });
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) stop(); else start();
        });
        reducedMotion.addEventListener('change', function (event) {
            if (event.matches) stop(); else start();
        });
    });
}());
