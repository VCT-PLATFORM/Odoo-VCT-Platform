/* JavaScript for VCT Portal Dashboard Interaction */

(function () {
    'use strict';

    function initPortalDashboard() {
        // 1. Particle creation (Floating Glassmorphism Spheres)
        var container = document.getElementById("vct_particles");
        if (container) {
            var colors = [
                "rgba(168, 85, 247, 0.15)", // Purple
                "rgba(236, 72, 153, 0.12)", // Pink
                "rgba(59, 130, 246, 0.12)",  // Blue
                "rgba(20, 184, 166, 0.12)"   // Teal
            ];
            
            for (var i = 0; i < 6; i++) {
                var bubble = document.createElement("div");
                bubble.className = "vct_bubble";
                var size = Math.floor(Math.random() * 300) + 200; // 200px - 500px
                bubble.style.width = size + "px";
                bubble.style.height = size + "px";
                bubble.style.left = Math.floor(Math.random() * 90) + "%";
                bubble.style.top = Math.floor(Math.random() * 90) + "%";
                bubble.style.background = "radial-gradient(circle, " + colors[i % colors.length] + " 0%, transparent 70%)";
                
                var animDuration = Math.random() * 25 + 25; // 25s - 50s
                bubble.style.transition = "all " + animDuration + "s ease-in-out";
                container.appendChild(bubble);
                
                // Closure for bubble floating movement loop
                (function (b, duration) {
                    function moveBubble() {
                        b.style.left = Math.floor(Math.random() * 90) + "%";
                        b.style.top = Math.floor(Math.random() * 90) + "%";
                    }
                    setTimeout(moveBubble, 100);
                    setInterval(moveBubble, duration * 1000);
                })(bubble, animDuration);
            }
        }
        
        // 2. 3D Tilt Effect on cards (Mouse interaction)
        var cards = document.querySelectorAll(".vct_app_card");
        cards.forEach(function (card) {
            card.addEventListener("mousemove", function (e) {
                var rect = card.getBoundingClientRect();
                var x = e.clientX - rect.left;
                var y = e.clientY - rect.top;
                
                var centerX = rect.width / 2;
                var centerY = rect.height / 2;
                
                // Max tilt is 8 degrees to keep it elegant and subtle
                var rotateX = -(y - centerY) / (rect.height / 8);
                var rotateY = (x - centerX) / (rect.width / 8);
                
                card.style.transform = "scale(1.08) translateY(-6px) rotateX(" + rotateX + "deg) rotateY(" + rotateY + "deg)";
            });
            
            card.addEventListener("mouseleave", function () {
                card.style.transform = "scale(1) translateY(0) rotateX(0deg) rotateY(0deg)";
            });
        });
    }

    if (document.readyState === "complete" || document.readyState === "interactive") {
        initPortalDashboard();
    } else {
        document.addEventListener("DOMContentLoaded", initPortalDashboard);
    }
})();
