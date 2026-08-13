/* Shared particle background system */
(function() {
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;

  const ctx = canvas.getContext('2d');
  let particles = [];
  let animFrame = null;

  const CONFIG = {
    count: window.PARTICLE_COUNT || 60,
    color: window.PARTICLE_COLOR || 'rgba(125,211,252,',
    speed: window.PARTICLE_SPEED || 0.3,
    sizeMin: 0.5,
    sizeMax: 2,
    opacityMin: 0.1,
    opacityMax: 0.5,
  };

  function resize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  class Particle {
    constructor() { this.reset(); }
    reset() {
      this.x = Math.random() * canvas.width;
      this.y = Math.random() * canvas.height;
      this.size = Math.random() * (CONFIG.sizeMax - CONFIG.sizeMin) + CONFIG.sizeMin;
      this.opacity = Math.random() * (CONFIG.opacityMax - CONFIG.opacityMin) + CONFIG.opacityMin;
      this.speedX = (Math.random() - 0.5) * CONFIG.speed * 2;
      this.speedY = (Math.random() - 0.5) * CONFIG.speed * 2;
    }
    update() {
      this.x += this.speedX;
      this.y += this.speedY;
      if (this.x < 0 || this.x > canvas.width || this.y < 0 || this.y > canvas.height) {
        this.reset();
      }
    }
    draw() {
      ctx.beginPath();
      ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
      ctx.fillStyle = `${CONFIG.color}${this.opacity})`;
      ctx.fill();
    }
  }

  function init() {
    resize();
    window.addEventListener('resize', resize);
    particles = [];
    for (let i = 0; i < CONFIG.count; i++) {
      particles.push(new Particle());
    }
    if (animFrame) cancelAnimationFrame(animFrame);
    animate();
  }

  function animate() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (const p of particles) {
      p.update();
      p.draw();
    }
    animFrame = requestAnimationFrame(animate);
  }

  // Start when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
