/* Ambient constellation field — blue/gold network motion behind the
   navigation rail and the overview hero. Local only, no dependencies.
   Respects prefers-reduced-motion, tab visibility and DPR. */
(function () {
    const canvases = document.querySelectorAll('.ambient-field');
    if (!canvases.length) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (reducedMotion.matches) return;

    const BLUE = '134, 180, 251';
    const GOLD = '216, 185, 111';
    const LINK_DISTANCE = 118;

    canvases.forEach(function (canvas, canvasIndex) {
        const surface = canvas.parentElement;
        const context = canvas.getContext('2d', { alpha: true });
        if (!surface || !context) return;

        let nodes = [];
        let width = 1;
        let height = 1;
        let frameHandle = null;
        let lastFrame = 0;
        const pointer = { x: -9999, y: -9999 };

        function density() {
            const area = width * height;
            return Math.max(18, Math.min(70, Math.round(area / 14000)));
        }

        function seed() {
            nodes = Array.from({ length: density() }, function (_, i) {
                return {
                    x: Math.random() * width,
                    y: Math.random() * height,
                    vx: (Math.random() - 0.5) * 0.28,
                    vy: (Math.random() - 0.5) * 0.28,
                    r: 0.9 + Math.random() * 1.7,
                    gold: (i + canvasIndex) % 7 === 0
                };
            });
        }

        function resize() {
            const bounds = surface.getBoundingClientRect();
            const ratio = Math.min(window.devicePixelRatio || 1, 1.75);
            width = Math.max(1, bounds.width);
            height = Math.max(1, bounds.height);
            canvas.width = Math.round(width * ratio);
            canvas.height = Math.round(height * ratio);
            context.setTransform(ratio, 0, 0, ratio, 0, 0);
            seed();
        }

        function step() {
            for (let i = 0; i < nodes.length; i += 1) {
                const node = nodes[i];
                node.x += node.vx;
                node.y += node.vy;

                if (node.x < -12) node.x = width + 12;
                if (node.x > width + 12) node.x = -12;
                if (node.y < -12) node.y = height + 12;
                if (node.y > height + 12) node.y = -12;

                const dx = node.x - pointer.x;
                const dy = node.y - pointer.y;
                const dist = Math.hypot(dx, dy);
                if (dist < 130 && dist > 0.01) {
                    node.x += (dx / dist) * 0.7;
                    node.y += (dy / dist) * 0.7;
                }
            }
        }

        function draw() {
            context.clearRect(0, 0, width, height);

            for (let i = 0; i < nodes.length; i += 1) {
                const a = nodes[i];
                for (let j = i + 1; j < nodes.length; j += 1) {
                    const b = nodes[j];
                    const dx = a.x - b.x;
                    const dy = a.y - b.y;
                    const dist = Math.hypot(dx, dy);
                    if (dist > LINK_DISTANCE) continue;
                    const alpha = (1 - dist / LINK_DISTANCE) * 0.42;
                    const goldLink = a.gold || b.gold;
                    context.strokeStyle = 'rgba(' + (goldLink ? GOLD : BLUE) + ',' + alpha.toFixed(3) + ')';
                    context.lineWidth = goldLink ? 0.9 : 0.7;
                    context.beginPath();
                    context.moveTo(a.x, a.y);
                    context.lineTo(b.x, b.y);
                    context.stroke();
                }
            }

            for (let k = 0; k < nodes.length; k += 1) {
                const node = nodes[k];
                const tint = node.gold ? GOLD : BLUE;
                context.beginPath();
                context.fillStyle = 'rgba(' + tint + ',0.85)';
                context.arc(node.x, node.y, node.r, 0, Math.PI * 2);
                context.fill();

                context.beginPath();
                context.fillStyle = 'rgba(' + tint + ',0.14)';
                context.arc(node.x, node.y, node.r * 4.5, 0, Math.PI * 2);
                context.fill();
            }
        }

        function frame(timestamp) {
            frameHandle = null;
            if (document.hidden || reducedMotion.matches) return;
            if (timestamp - lastFrame < 33) {
                frameHandle = window.requestAnimationFrame(frame);
                return;
            }
            lastFrame = timestamp;
            step();
            draw();
            frameHandle = window.requestAnimationFrame(frame);
        }

        function start() {
            if (!document.hidden && !reducedMotion.matches && frameHandle === null) {
                frameHandle = window.requestAnimationFrame(frame);
            }
        }

        function stop() {
            if (frameHandle !== null) window.cancelAnimationFrame(frameHandle);
            frameHandle = null;
        }

        function onPointerMove(event) {
            const bounds = canvas.getBoundingClientRect();
            pointer.x = event.clientX - bounds.left;
            pointer.y = event.clientY - bounds.top;
        }

        function onPointerLeave() {
            pointer.x = -9999;
            pointer.y = -9999;
        }

        resize();
        start();
        window.addEventListener('resize', resize, { passive: true });
        surface.addEventListener('pointermove', onPointerMove, { passive: true });
        surface.addEventListener('pointerleave', onPointerLeave, { passive: true });
        document.addEventListener('visibilitychange', function () {
            if (document.hidden) stop(); else start();
        });
        reducedMotion.addEventListener('change', function (event) {
            if (event.matches) stop(); else start();
        });
    });
}());
