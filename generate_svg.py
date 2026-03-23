import math
import os

w, h = 1024, 576
cx, cy = 512, 288

svg = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg viewBox="0 0 {w} {h}" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
<defs>
    <!-- Background Brush -->
    <filter id="brushedMetal">
      <feTurbulence type="fractalNoise" baseFrequency="0.005 0.2" numOctaves="3" result="noise" />
      <feColorMatrix type="matrix" values="0.1 0 0 0 0.85
                                           0.1 0 0 0 0.85
                                           0.1 0 0 0 0.85
                                           0   0 0 0.4 0" result="colNoise" />
      <feBlend in="SourceGraphic" in2="colNoise" mode="multiply" />
    </filter>

    <!-- Glow for Orange Ring -->
    <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="8" result="blur" />
      <feMerge>
        <feMergeNode in="blur" />
        <feMergeNode in="blur" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>

    <!-- Dial Drop Shadow -->
    <filter id="dropShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="25" stdDeviation="25" flood-color="#000" flood-opacity="0.8" />
    </filter>
    
    <filter id="dropShadowLight" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="5" stdDeviation="5" flood-color="#000" flood-opacity="0.6" />
    </filter>

    <!-- Screws Shadow -->
    <filter id="screwShadow">
      <feDropShadow dx="1" dy="1" stdDeviation="1" flood-color="#fff" flood-opacity="0.2" result="light" />
      <feDropShadow dx="-1" dy="-1" stdDeviation="1" flood-color="#000" flood-opacity="0.8" in="SourceGraphic" result="dark" />
      <feMerge>
        <feMergeNode in="light" />
        <feMergeNode in="dark" />
        <feMergeNode in="SourceGraphic" />
      </feMerge>
    </filter>

    <linearGradient id="bgGrad" x1="0" y1="0" x2="1024" y2="576" gradientUnits="userSpaceOnUse">
        <stop offset="0%" stop-color="#cfd0d2" />
        <stop offset="50%" stop-color="#9a9b9d" />
        <stop offset="100%" stop-color="#b6b8ba" />
    </linearGradient>

    <!-- Knurling Pattern -->
    <pattern id="knurl" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
        <rect width="6" height="6" fill="#151515" />
        <path d="M 0,0 L 3,3 L 6,0 Z" fill="#080808" />
        <path d="M 0,6 L 3,3 L 6,6 Z" fill="#303030" />
        <path d="M 0,0 L 3,3 L 0,6 Z" fill="#111111" />
        <path d="M 6,0 L 3,3 L 6,6 Z" fill="#222222" />
    </pattern>

    <linearGradient id="dialRim" x1="30%" y1="0%" x2="70%" y2="100%">
        <stop offset="0%" stop-color="#666" />
        <stop offset="20%" stop-color="#444" />
        <stop offset="80%" stop-color="#2a2a2a" />
        <stop offset="100%" stop-color="#111" />
    </linearGradient>

    <radialGradient id="dialCenter" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stop-color="#9a9a9a" />
        <stop offset="30%" stop-color="#7a7a7a" />
        <stop offset="80%" stop-color="#444" />
        <stop offset="100%" stop-color="#2a2a2a" />
    </radialGradient>
    
    <!-- Conic gradient approximation for metal shine -->
    <linearGradient id="conic1" x1="30%" y1="0%" x2="70%" y2="100%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.6)"/>
        <stop offset="40%" stop-color="rgba(0,0,0,0.0)"/>
        <stop offset="50%" stop-color="rgba(0,0,0,0.4)"/>
        <stop offset="60%" stop-color="rgba(0,0,0,0.0)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0.3)"/>
    </linearGradient>
    <linearGradient id="conic2" x1="0%" y1="30%" x2="100%" y2="70%">
        <stop offset="0%" stop-color="rgba(255,255,255,0.4)"/>
        <stop offset="40%" stop-color="rgba(0,0,0,0.0)"/>
        <stop offset="50%" stop-color="rgba(0,0,0,0.2)"/>
        <stop offset="60%" stop-color="rgba(0,0,0,0.0)"/>
        <stop offset="100%" stop-color="rgba(255,255,255,0.5)"/>
    </linearGradient>

    <!-- Torx Screw -->
    <g id="torxScrew">
        <!-- Screw base hole shadow -->
        <circle r="12" fill="#111" filter="url(#dropShadowLight)" />
        <circle r="11" fill="url(#dialRim)" stroke="#2a2a2a" stroke-width="1.5" />
        <!-- Torx star -->
        <path d="M 0,-4.5 L 1.5,-2 L 4.5,-2 L 2.5,0 L 4.5,2 L 1.5,2 L 0,4.5 L -1.5,2 L -4.5,2 L -2.5,0 L -4.5,-2 L -1.5,-2 Z" fill="#0a0a0a" filter="url(#screwShadow)"/>
    </g>
</defs>

<!-- Background Panel -->
<rect width="100%" height="100%" fill="url(#bgGrad)" filter="url(#brushedMetal)" />

<!-- Background Grid Lines -->
<g stroke="rgba(0,0,0,0.15)" stroke-width="1.2">
    <line x1="0" y1="288" x2="1024" y2="288" />
    <line x1="512" y1="0" x2="512" y2="576" />
'''

r1, r2 = 290, 480
svg += f'<circle cx="{cx}" cy="{cy}" r="{r1}" stroke="rgba(0,0,0,0.05)" stroke-width="1.5" fill="none" />\n'
svg += f'<circle cx="{cx}" cy="{cy}" r="{r2}" stroke="rgba(0,0,0,0.05)" stroke-width="1.5" fill="none" />\n'

for deg in range(0, 360, 45):
    rad = math.radians(deg)
    x1 = cx + math.cos(rad) * 200
    y1 = cy + math.sin(rad) * 200
    x2 = cx + math.cos(rad) * 1000
    y2 = cy + math.sin(rad) * 1000
    svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="rgba(0,0,0,0.06)" stroke-width="1.5" />\n'

svg += '</g>\n'

# Ticks and Labels
svg += '<g id="tickMarks" stroke="#333" stroke-width="1.5">\n'

for i in range(360):
    if i % 2 != 0: continue # fewer ticks to look right
    
    rad = math.radians(i - 90) # 0 at top
    length = 215
    if i % 10 == 0:
        length = 225
        if i % 30 == 0:
            length = 235
            # Text
            tx = cx + math.cos(rad) * 255
            ty = cy + math.sin(rad) * 255
            rot = i
            if rot > 90 and rot < 270:
                rot -= 180
            svg += f'<text x="{tx}" y="{ty}" font-family="Consolas, monospace" font-size="14" font-weight="500" fill="#2a2a2a" text-anchor="middle" dominant-baseline="middle" transform="rotate({rot}, {tx}, {ty})">{i}°</text>\n'
    
    x1 = cx + math.cos(rad) * 200
    y1 = cy + math.sin(rad) * 200
    x2 = cx + math.cos(rad) * length
    y2 = cy + math.sin(rad) * length
    sw = 2 if i % 10 == 0 else 1
    svg += f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" stroke-width="{sw}" />\n'
svg += '</g>\n'

# Outer Shadow Ring
svg += f'<circle cx="{cx}" cy="{cy}" r="195" fill="#050505" filter="url(#dropShadow)" />\n'

# Bright Orange Ring
svg += f'<circle cx="{cx}" cy="{cy}" r="192" stroke="#ff5500" stroke-width="6" fill="none" filter="url(#glow)" />\n'
svg += f'<circle cx="{cx}" cy="{cy}" r="192" stroke="#ffaa88" stroke-width="2" fill="none" />\n'

# Knurled Ring Base
svg += f'<circle cx="{cx}" cy="{cy}" r="162" stroke="#111" stroke-width="58" fill="none" />\n'
svg += f'<circle cx="{cx}" cy="{cy}" r="162" stroke="url(#knurl)" stroke-width="56" fill="none" />\n'

# Knurling Sphere shading (Top and bottom shadows)
svg += f'<circle cx="{cx}" cy="{cy}" r="185" stroke="rgba(0,0,0,0.8)" stroke-width="12" fill="none" />\n'
svg += f'<circle cx="{cx}" cy="{cy}" r="140" stroke="rgba(0,0,0,0.9)" stroke-width="10" fill="none" />\n'
svg += f'<circle cx="{cx}" cy="{cy}" r="162" stroke="rgba(255,255,255,0.05)" stroke-width="20" fill="none" />\n'


# Main inner dial
svg += f'<circle cx="{cx}" cy="{cy}" r="135" fill="url(#dialRim)" stroke="#050505" stroke-width="2" filter="url(#dropShadowLight)" />\n'
svg += f'<circle cx="{cx}" cy="{cy}" r="125" fill="#000" />\n'
svg += f'<circle cx="{cx}" cy="{cy}" r="123" fill="url(#dialCenter)" />\n'

# Metal sheen overlay
svg += f'<circle cx="{cx}" cy="{cy}" r="123" fill="url(#conic1)" />\n'
svg += f'<circle cx="{cx}" cy="{cy}" r="123" fill="url(#conic2)" style="mix-blend-mode: overlay;" />\n'

# Subdued Central point 
svg += f'<circle cx="{cx}" cy="{cy}" r="1" fill="#fff" opacity="0.6" />\n'

# Arrow Indicator (pointing left)
svg += f'<polygon points="{cx-105},{cy} {cx-93},{cy-7} {cx-93},{cy+7}" fill="#555" stroke="#222" stroke-width="1.5" filter="url(#screwShadow)" />\n'

# Torx Screws
for i in range(6):
    rad = math.radians(i * 60 + 30) # Offset to match reference image angles
    sx = cx + math.cos(rad) * 90
    sy = cy + math.sin(rad) * 90
    svgt = f'translate({sx}, {sy}) rotate({i*60 + 30})'
    svg += f'<use href="#torxScrew" transform="{svgt}" />\n'


# Top Left Box (Transparent Glass effect)
svg += """
<g transform="translate(40, 40)">
    <rect x="0" y="0" width="320" height="85" fill="rgba(200,200,200,0.15)" stroke="rgba(0,0,0,0.5)" stroke-width="1.5" />
    <line x1="0" y1="42.5" x2="320" y2="42.5" stroke="rgba(0,0,0,0.4)" stroke-width="1.5" />
    
    <text x="15" y="28" font-family="Consolas, monospace" font-size="20" font-weight="500" fill="#1a1a1a" letter-spacing="1">SYNTHETIC LOGISTICS 2024</text>
    <text x="15" y="70" font-family="Consolas, monospace" font-size="20" font-weight="500" fill="#1a1a1a" letter-spacing="1">HAPTIC_CTRL // UNIT-01</text>
    
    <!-- connecting line -->
    <line x1="320" y1="42.5" x2="400" y2="105" stroke="rgba(0,0,0,0.4)" stroke-width="1.5" />
</g>
"""

# Small diamond logo bottom right
svg += """
<g transform="translate(980, 520)">
    <path d="M 0,-20 Q 3,-3  20,0 Q 3,3 0,20 Q -3,3 -20,0 Q -3,-3 0,-20 Z" fill="#dddddd" filter="url(#dropShadowLight)" />
    <circle cx="0" cy="0" r="3" fill="#fff" />
</g>
"""

svg += '</svg>'

out_path = 'c:\\\\Projects\\\\Business\\\\Web_projects_NEW\\\\dashboard\\\\haptic_dial.svg'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(svg)
print(f"SVG saved to {out_path}")
