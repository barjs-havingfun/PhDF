// Which OCR languages to use, downloading their data files on first use.
import { api } from "./api";
import { notify } from "./notify.svelte";

export async function ocrLanguages(): Promise<string[]> {
  const py = await api();
  const { installed } = await py.ocr_info();
  const chosen = ((await py.get_setting<string[]>("ocr.languages", [])) ?? []).filter((l) =>
    installed.includes(l),
  );
  if (chosen.length) return chosen;

  // First use: English, plus Turkish on a Turkish system.
  const wanted = navigator.language.toLowerCase().startsWith("tr") ? ["eng", "tur"] : ["eng"];
  for (const lang of wanted.filter((l) => !installed.includes(l))) {
    notify.show({ text: `Downloading OCR language data (${lang})…` }, 60000);
    await py.ocr_download(lang);
  }
  notify.clear();
  await py.set_setting("ocr.languages", wanted);
  return wanted;
}
