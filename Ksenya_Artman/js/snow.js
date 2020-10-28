

// NEPHAELIN
// Title: Moon Dust
// Author: Ivor Anderson

$(function (canv, particleSize = 4, particleCount = 200, interval = 200, W = window.innerWidth, H = window.innerHeight) {

var W, H, canvas, ctx, particles = [];

    W = W
    H = H
    var canvas = canv;
    canvas.width = W;
    canvas.height = H;
    
canvas = $("#canvasOne").get(0);
    canvas.width = W;
    canvas.height = H;

ctx = canvas.getContext("2d");
ctx.globalCompositeOperation = "lighter";

    var mouse = {
      x: 0, 
      y: 0,
      rx:0,
      ry:0
    };
    
var counter = 0;
            
function randomNorm(mean, stdev) {
                
return Math.abs(Math.round((Math.random()*2-1)+(Math.random()*2-1)+(Math.random()*2-1))*stdev)+mean;
}


function Particle() {
//---------------------- PARTICLE COLORS
this.h = parseInt( 16, 10);
this.s = parseInt( 100 * Math.random() + 30, 10);
this.l = parseInt( 50 * Math.random() + 30, 10);
this.a = .9 * Math.random();

this.color = "#f4e9e5";
this.shadowcolor = "rgba(255, 231, 200, 0.1)";
//--------------------------------------                

this.x = Math.random() * W;
this.y = Math.random() * H;
this.direction = {
     "x": -1 + Math.random() * 2,
     "y": -1 + Math.random() * 2
};

this.radius=randomNorm(0,particleSize);
this.scale=0.7*Math.random()+0.5;
this.rotation=Math.PI/4*Math.random();
      
this.grad=ctx.createRadialGradient( this.x, this.y, this.radius, this.x, this.y, 0 );

  this.grad.addColorStop(0,this.color);
  this.grad.addColorStop(1,this.shadowcolor);
      
  this.vx = (2 * Math.random() + 4)*.01*this.radius;
  this.vy = (2 * Math.random() + 4)*.01*this.radius;
        
this.valpha = 0.01*Math.random()-0.02;
        
this.move = function () {
this.x += this.vx * this.direction.x;
this.y += this.vy * this.direction.y;
this.rotation+=this.valpha;
};

this.changeDirection = function (axis) {
            this.direction[axis] *= -1;
            this.valpha *= -1;
        };
        this.draw = function () {
            ctx.save();
            ctx.translate(this.x+mouse.rx/-20*this.radius,this.y+mouse.ry/-20*this.radius);  
          ctx.rotate(this.rotation);  
          ctx.scale(1,this.scale);
            
            this.grad=ctx.createRadialGradient( 0, 0, this.radius, 0, 0, 0 );
            this.grad.addColorStop(1,this.color);
            this.grad.addColorStop(0,this.shadowcolor);
            ctx.beginPath();
            ctx.fillStyle = this.grad;
            ctx.arc(0, 0, this.radius, 0, Math.PI * 2, false);
            ctx.fill();
            ctx.restore();
   
        };
this.boundaryCheck = function () {
            if (this.x >= W*1.2) {
                this.x = W*1.2;
                this.changeDirection("x");
            } else if (this.x <= -W*0.2) {
                this.x = -W*0.2;
                this.changeDirection("x");
            }
            if (this.y >= H*1.2) {
                this.y = H*1.2;
                this.changeDirection("y");
            } else if (this.y <= -H*0.2) {
                this.y = -H*0.2;
                this.changeDirection("y");
            }
        };
    }

    function clearCanvas() {
        ctx.clearRect(0, 0, W, H);
    }

    function createParticles() {
        for (var i = particleCount - 1; i >= 0; i--) {
            p = new Particle();
            particles.push(p);
        }
    }
    function drawParticles() {
        for (var i = particleCount - 1; i >= 0; i--) {
            p = particles[i];
            p.draw();
        }

      
    }

    function updateParticles() {
        for (var i = particles.length - 1; i >= 0; i--) {
            p = particles[i];
            p.move();
            p.boundaryCheck();

        }
    }

    function initParticleSystem() {
        createParticles();
        drawParticles();
    }

    function animateParticles() {
        clearCanvas();
        setDelta();
        update()
        drawParticles();
        updateParticles();
        requestAnimationFrame(animateParticles);
    }
  
    initParticleSystem();
    requestAnimationFrame(animateParticles);
  
    function setDelta() {  
      this.now    =   (new Date()).getTime();  
      mouse.delta  =   (this.now-this.then)/1000;  
      this.then   =   this.now;  
    }
    function update() {  
 
    if(isNaN(mouse.delta) || mouse.delta <= 0) { return; }  
 
    var distX   =   mouse.x - (mouse.rx),  
        distY   =   mouse.y - (mouse.ry);  

    if(distX !== 0 && distY !== 0) {          
 
        mouse.rx -=  ((mouse.rx - mouse.x) / mouse.speed); 
        mouse.ry -=  ((mouse.ry - mouse.y) / mouse.speed); 
         
    }   
  
};  

});



