#!/usr/bin/env python3
"""Replace emojis with SVG icons in dashboard."""

with open('demo/dashboard.py', 'r') as f:
    content = f.read()

# Replace the icons8 URL with custom SVG
content = content.replace(
    'st.image("https://img.icons8.com/fluency/96/bank-building.png", width=64)',
    '''# Custom SVG Logo
import pathlib
icon_path = pathlib.Path(__file__).parent / "icons" / "vyapaar_logo.svg"
if icon_path.exists():
    with open(icon_path, 'r') as f:
        logo_svg = f.read().replace('width="200"', 'width="80"').replace('height="200"', 'height="80"')
    st.markdown(f'<div style="text-align:center;">{logo_svg}</div>', unsafe_allow_html=True)
else:
    st.image("https://img.icons8.com/fluency/96/bank-building.png", width=64)'''
)

with open('demo/dashboard.py', 'w') as f:
    f.write(content)

print("Replaced logo with SVG!")
