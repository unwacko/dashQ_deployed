cd /private/tmp/claude-501/-Users-main-Everything-Programming-vibecoding-prac-dash-Q/08f3c9b7-be96-4c30-a002-15ef5ede2c2f/scratchpad/deck
python3 -c "
import glob,os
h=open('deck.src.html').read()
for f in glob.glob('charts/*.svg'): h=h.replace('{{%s}}'%os.path.basename(f)[:-4], open(f).read())
open('deck.html','w').write(h)"
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --no-pdf-header-footer --allow-file-access-from-files --print-to-pdf=/private/tmp/claude-501/-Users-main-Everything-Programming-vibecoding-prac-dash-Q/08f3c9b7-be96-4c30-a002-15ef5ede2c2f/scratchpad/deck/dashQ_deck.pdf file:///private/tmp/claude-501/-Users-main-Everything-Programming-vibecoding-prac-dash-Q/08f3c9b7-be96-4c30-a002-15ef5ede2c2f/scratchpad/deck/deck.html 2>/dev/null
/private/tmp/claude-501/-Users-main-Everything-Programming-vibecoding-prac-dash-Q/08f3c9b7-be96-4c30-a002-15ef5ede2c2f/scratchpad/deck/../v/bin/python -c "
import pymupdf
src=pymupdf.open('dashQ_deck.pdf'); print(len(src),'pages')
for s in range(0,len(src),6):
    out=pymupdf.open(); pg=out.new_page(width=1440,height=1215)
    for j in range(6):
        i=s+j
        if i>=len(src): break
        pg.show_pdf_page(pymupdf.Rect((j%2)*720,(j//2)*405,(j%2)*720+720,(j//2)*405+405),src,i)
    pg.get_pixmap(dpi=110).save('m%d.png'%(s//6))
"
