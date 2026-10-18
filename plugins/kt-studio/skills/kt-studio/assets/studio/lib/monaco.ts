// Helpers for apps that embed a Monaco editor (YAML, JSON, SQL editors and similar).
// Never type into Monaco with the keyboard on camera: auto-indent and auto-close break the text.
import type { Page } from '@playwright/test';
import { zoomTo, showOverlay, type NarrationTimeline } from '@argo-video/cli';
import { PAUSE_AFTER_POINT } from './pacing';

declare global {
  interface Window {
    monaco: any;
    __kt: {
      prepare(fontSize?: number): void;
      typeIn(text: string, msPerLine: number): Promise<void>;
      highlight(ranges: [number, number][], className: string): void;
      clear(): void;
    };
  }
}

/** Waits for Monaco, then installs window.__kt: clear, line-by-line "typing", line highlight. */
export async function installMonacoHelpers(page: Page) {
  await page.waitForFunction(() => window.monaco?.editor?.getEditors?.().length > 0, null, { timeout: 60_000 });
  await page.evaluate(() => {
    const style = document.createElement('style');
    style.textContent = `
      .kt-hl { background: rgba(255, 184, 0, .30) !important; }
      .kt-bad { background: rgba(255, 72, 72, .30) !important; }
      #kt-focus { position: fixed; pointer-events: none; }`;
    document.head.appendChild(style);
    const editor = () => window.monaco.editor.getEditors()[0];
    let decorations: any = null;
    window.__kt = {
      prepare(fontSize = 15) {
        editor().updateOptions({ fontSize, lineHeight: Math.round(fontSize * 1.6) });
        const model = editor().getModel();
        model.pushEditOperations([], [{ range: model.getFullModelRange(), text: '' }], () => null);
      },
      async typeIn(text, msPerLine) {
        const model = editor().getModel();
        for (const line of text.split('\n')) {
          const end = model.getFullModelRange().getEndPosition();
          const range = new window.monaco.Range(end.lineNumber, end.column, end.lineNumber, end.column);
          model.pushEditOperations([], [{ range, text: (model.getValueLength() ? '\n' : '') + line }], () => null);
          await new Promise((resolve) => setTimeout(resolve, msPerLine));
        }
        // Many apps tint the block that holds the caret; park it on line 1.
        editor().setPosition({ lineNumber: 1, column: 1 });
        (document.activeElement as HTMLElement | null)?.blur();
      },
      highlight(ranges, className) {
        const ed = editor();
        decorations?.clear();
        decorations = ed.createDecorationsCollection(
          ranges.map(([from, to]) => ({ range: new window.monaco.Range(from, 1, to, 1), options: { isWholeLine: true, className } })),
        );
        // A fixed box over the lines gives zoomTo something to aim at.
        const box = ed.getDomNode().getBoundingClientRect();
        const { contentLeft } = ed.getLayoutInfo();
        const lineHeight = ed.getOption(window.monaco.editor.EditorOption.lineHeight);
        const top = Math.min(...ranges.map(([from]) => ed.getTopForLineNumber(from))) - ed.getScrollTop();
        const bottom = Math.max(...ranges.map(([, to]) => ed.getTopForLineNumber(to))) + lineHeight - ed.getScrollTop();
        const focus = document.getElementById('kt-focus') ?? document.body.appendChild(document.createElement('div'));
        focus.id = 'kt-focus';
        Object.assign(focus.style, {
          left: `${box.left + contentLeft - 12}px`,
          top: `${box.top + top - 8}px`,
          width: '640px',
          height: `${bottom - top + 16}px`,
        });
      },
      clear() {
        decorations?.clear();
      },
    };
  });
}

/** Highlight lines, zoom on them after export, show the scene's overlay, wait for the voice. */
export async function explainLines(page: Page, narration: NarrationTimeline, scene: string, ranges: [number, number][], className = 'kt-hl') {
  narration.mark(scene);
  await page.evaluate(({ ranges, className }) => window.__kt.highlight(ranges, className), { ranges, className });
  const length = narration.sceneDuration(scene);
  zoomTo(page, '#kt-focus', { narration, scale: 1.45, duration: length, fadeIn: 700, fadeOut: 700, holdMs: Math.max(0, length - 1400) });
  await showOverlay(page, scene, narration.durationFor(scene, PAUSE_AFTER_POINT));
}
