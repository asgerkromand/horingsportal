
# To-do
* Setup QWEN 2.5 VL 72B up on the server

# 3/2/2025

0 Re-scrape

```python
python scripts/scrape.py --data-dir data --all
```

1. Make a table of Horingssvar per year and department
2. Counting the distribution of file-formats to the "høringssvar"-files.

```bash
grep -roh "svar" --include="*" . | awk -F. '{ext=$NF} ext!=""{count[ext]++} END {for (e in count) print e, count[e]}'
```

## Test set (pdf-segmentation)

1. Does a model know how (i.e. where) to segment a pdf?
2. Andet approach er, at model skal predicte for hver side, hvilken organisation der er afsender.
3. Lav et test-set med variation, dvs. forskellige længder og formater.

## Test set (content)

1. Sample on year and departments to manually check file content and structure
2. Construct a test set with the relevant information you want to extract so that you capture enough variation in the different formats and structures

## Model specification

- OCR:
  - Rule-based extraction
  - VISION-AI
    - Open-source?
    - Domæne?
  - OpenAI?

- Multi-step pipeline:
  - "En pdf fil med 30 høringssvar"
    - Prompt 1: "Del denne pdf med 30 høringssvar op i 30 filer - én pr. organisation"
      - Er med til at increase performance?
- Læs om potentielle modeller bruger OCR
  - Det kan være, at jeg får svært ved at parse footters og header, hvis de ligger som billeder
  - Løsning kan så måske være, at splitte pdf'erne op og så konverte til png, og så bruge en multi-modal, som ikke fucker med OCR.
- Hvordan skal jeg repræsentere data?
  - Som pdf?
    - Binary-format.
  - Som png?
    - Multi-modal
    - En side af gangen. Hvem er afsenderen?
    - Måske man kan lave det til en binary classification task, hvor man tager to sider af gangen, og så skal modellen finde ud af, om den skal splitte eller ej.

## Model-Garage

### MMM

- https://github.com/QwenLM/Qwen2.5-VL
  - https://github.com/QwenLM/Qwen2.5-VL?tab=readme-ov-file
  - Har potentiale
- https://allenai.org/multimodal-models

### File-parser

- https://github.com/Filimoa/open-parse

# 10/2/25

## file-domain count function and results

```bash
find . -type f \( -iname "*ringssvar*" -o -iname "*ringsvar*" \) 2>/dev/null | awk -F. '{if (NF>1) print $NF}' | sort | uniq -c | sort -nr"
```

Count results of summing file domains on responses:

* 8978 pdf:
  * ./60749/L_17_H�ringssvar ./65009/H�ringssvar ./65835/H�ringssvar ./68716/H�ringssvar ./59051/H�ringssvar_til_h�ring_af_ændring_af_milj�beskyttelsesloven_-_landskabsh...
* 349 PDF:
  * ./13419/H�ringssvar ./10633/KL�s_h�ringssvar ./15187/H�ringssvar_-_Advokatsamfundet_-_bemærkninger_DOK591475 ./42283/Hoeringssvar ./12163/h�ringssvar_samlet_1
* 166 msg:
  * ./61498/H�ringssvar_Justitsministeriet ./61498/Samlet_oversigt_over_Geodatastyrelsens_supplerende_bemærkninger_til_modtagne_h�ringssvar ./61498/H�ringssvar_Erhvervsministeriet ./61498/H�ringssvar_Kommissarius_for_Statens_ekspropriationer_på_�erne ./61498/H�ringssvar_DSB
* 136 doc:
  * ./11143/h�ringssvar_bek_fjervildt_aug06 ./11978/dodsboh�ringssvar ./11520/H�ringssvar_Forening_for_Prydfjerrkræ ./11520/H�ringssvar_fugleinfluenza_26_02_06 ./11520/Dyrenes_Beskyttelse_h�ringssvar
* 79 DOC:
  * ./15180/H�ringssvar_Landbrug_og_F�devarer ./15180/H�ringssvar_Håndværksrådet ./10604/H�ringssvar_e-indkomst.doc ./10604/ctmpGWViewerCaptiaHringssvar-eIndkomst-OSO�S�.doc ./10604/H�ringssvar_eIndkomst.doc
* 78 docx:
  * ./14407/Betaling_-_h�ringssvar ./60586/Skabelon_til_h�ringssvar_BR18 ./60586/Skabelon_til_h�ringssvar_certificeringsbekendtg�relsen ./61858/Hermed_h�ringssvar_på_vegne_af_HBL ./61858/h�ringssvar_betalingsbekendtg�relse
* 37 TXT:
  * ./11520/H�ringssvar_Viva_Sternsdorf ./11520/H�ringssvar_Byhavenetværket ./11520/H�ringssvar_Ninna_Falkesgaard ./11520/H�ringssvar_Kristin_Hammeren ./11348/H�ringssvar_fra_FRR
* 34 TIF:
  * ./11348/H�ringssvar_fra_Advokatrådet_-_ingen_bemærkn ./11499/H�ringssvar_Carlsberg ./11499/H�ringssvar_Assens_Tobaksfabrik ./11499/H�ringssvar_Dansk_Aktionærforening ./10796/H�ringssvar_fra_AES
* 28 xlsx:
  * ./60323/Kommentarskema_til_h�ringssvar ./36878/Kommentarskema_til_h�ringssvar_RUKS ./59480/10c_2016-05-27_Kommentarskema_til_h�ringssvar_AU_Health ./59480/5_Kommentarskema_til_h�ringssvar_Præhospitalsdatabasen ./59480/23_Danske_regioners_h�ringssvar
* 23 htm:
  * ./59716/H�ringssvar�_CO-industri ./59716/H�ringssvar�_Kommunernes_Landsforening ./59716/H�ringssvar�_Struer_Kommune ./11049/h�ringssvar_vedr._fugleinfluenza_Heine_Refsing ./62170/H�ringssvar_S�-_og_Handelsretten
* 18 pdf�1�:
  * ./12395/h�ringssvar ./12395/H�ringssvar3 ./12395/H�ringssvar1 ./12303/LO_H�ringssvar_300_timers_reglen ./14915/hoeringssvar_betalingstjenester
* 17 txt:
  * ./15180/H�ringssvar_DTU ./60866/Vallensbæk_Kommune_h�ringssvar ./60866/Region_Hovedstaden_h�ringssvar ./14033/H�ringssvar._3F ./14033/H�ringssvar._Danmarks_Fiskehandlere
* 12 tif:
  * ./10791/hoeringssvar_soemandsloven ./11041/H�ringssvar_-_Bek._om_disciplinærnævnet_for_ejendomsm ./11041/H�ringssvar_-_Ansvar__garantistillelse_og_beh._af_depon ./13207/Samlede_h�ringssvar ./11327/1._del_af_h�ringssvarene_og_h�ringslisten
* 10 oft:
  * ./11049/H�ringssvar_fra_Dansk_Land-_og_Strandjagt ./14556/H�ringssvar_Forbrugerrådet ./14556/H�ringssvar_Beskæftigelsesministeriet ./14556/H�ringssvar_Ministeriet_for_Videnskab�_Teknologi_og_Udvikling ./63942/Erhvervsstyrelsens_h�ringssvar_vedr._certifikatbekendtg�relsen_m.v._-_journalnummer_2020-16-31-00138
* 9 DOCX:
  * ./59460/Varefaktas_h�ringssvar_2016-27-31-00204 ./35833/Datatilsynet_h�ringssvar_�DOK1559818� ./17395/H�rringssvar_fra_DI_-_med_bemærkninger_�DOK30122560� ./64054/H�ringssvar_�ViSikrer� ./69543/Skabelon_til_h�ringssvar
* 5 zip:
  * ./15323/Telenor_h�ringssvar_M4_og_M5_markedsafgrænsning_og_markedsanalyse ./15323/H�ringssvar_fra_Telia_på_M4_og_M5_markedsafgrænsning_og_markedsanalyse ./15322/Telenor_h�ringssvar_M4_og_M5_markedsafgrænsning_og_markedsanalyse ./15322/H�ringssvar_fra_Telia_på_M4_og_M5_markedsafgrænsning_og_markedsanalyse ./15552/H�ringssvar_800
* 5 mht:
  * ./10106/10_H�ringssvar_u_bem_fra_Skatterevisorforeningen_1_vedhæftet_fil_HTM ./10106/11_H�ringssvar_u_bemærkn_fra_Ejendomsforeningen_Danmark_1_vedhæftet_fil_HTM ./15026/H�ringssvar_securities ./15026/H�ringssvar_dansk_rederiforening ./15026/H�ringssvar_SRF
* 5 HTM:
  * ./14873/h�ringssvar_fra_Danmarks_Lejerforeninger_ubem_DOK9740527 ./16604/H�ringssvar_fra_ATP_DOK11538024 ./16604/H�ringssvar_fra_F�P_DOK11587354 ./10106/8_h�ringssvar_u_bem_fra_ATP_4_vedhæftede_filer ./12325/H�ringssvar_fra_Dansk_Taxi_Råd_-_ingen_bemærkninger
* 4 doc�1�:
  * ./11978/dodsboh�ringssvar ./11725/H�ringssvar_roaming290607 ./11645/VS_H�ringssvar_om_bek._om_forsikring_eller_anden_garanti_til_dækning_af_det_privateretlige_ansvar_fo ./11041/Statisk_kopi_afH�ringssvar_-_ejendomsformidlingsbekendt
* 2 pdf�2�:
  * ./10005/klagenævn_hoeringssvar_samlet ./16448/Bilag_til_h�ringssvar_fra_Kommissarius_på_�erne_-_Bidrag_fra_Den_Ledende_Landinspekt�r_for_Statsbane
* 2 jpg:
  * ./62781/H�ringssvar_-_Milj�styrelsen_�bilag_1� ./62781/H�ringssvar_-_Milj�styrelsen_�bilag_2�
* 2 XLS:
  * ./11499/Bilag_til_h�ringssvar_F�P ./16670/Bilag_1_-_Liste_med_oversigt_over_h�ringssvar
* 1 rtf:
  * ./16448/H�ringssvar_fra_By-_og_Landskabsstyrelsen
* 1 ppt:
  * ./11316/Tillæg_7_til_Nordlite_h�ringssvar
* 1 XLSX:
  * ./15977/Bilag_til_h�ringssvar_fra_Dansk_Industri
* 1 DOc:
  * ./11499/H�ringssvar_DANVA_�Dansk_Vand-_og_Spildevandsforening�
* 1 DOT:
  * ./11017/H�ringssvar.dot
* 1 DOC�1�:
  * ./12325/H�ringssvar_fra_Dansk_Aktionærforening_�DAF�
* 1 /62633/H�ringssvar_Den_danske_Landinspekt�rforening:
* 1 /16177/H�ringssvar_Det_Dyreetiske_Råd:
* 1 /11453/H�ringssvar_-_Aarhus_Universitet:
* 1 /11015/H�ringssvar_9:
* 1 /11015/H�ringssvar_8:
* 1 /11015/H�ringssvar_7:
* 1 /11015/H�ringssvar_6:
* 1 /11015/H�ringssvar_5:
* 1 /11015/H�ringssvar_4:
* 1 /11015/H�ringssvar_3:
* 1 /11015/H�ringssvar_2:
* 1 /11015/H�ringssvar_1:
* 1 /11015/H�ringssvar_13:
* 1 /11015/H�ringssvar_12:
* 1 /11015/H�ringssvar_11:
* 1 /11015/H�ringssvar_10:
* 1 /10941/H�ringssvar_2:
* 1 /10471/6_h�ringssvar_-_AMVAB_Selskabsret:
* 1 /10471/3_h�ringssvar_-_AMVAB_Selskabsret:
* 1 /10470/5_h�ringssvar_-_AMVAB_ÅRL:
* 1 /10470/4_h�ringssvar_-_AMVAB_ÅRL:
* 1 /10470/2_h�ringssvar_-_AMVAB_ÅRL:
* 1 /10470/1_H�ringssvar_-_AMVAB_ÅRL:
* 1 /10200/Samlet_h�ringssvar:
* 1 /10105/Samlet_h�ringssvar_2:
* 1 /10104/Samlet_h�ringssvar_1:
* 1 /10041/H�ringssvar:

## Specs i forhold til mapper

**mapper i alt (antal høringer)** = 15852

**mapper der matcher på høringssvar** = 5392

*for videre exploratory data analysis see data_overview.ipynb*

## Kommentarer til høringssvar med forskellige fil-formatter

**.xlsx**

* Det kan være en god ide at få fremsøgt alle foldere med .xlsx filer.
* Når der er .xlsx filer i en subfolder, så tyder det på, at der fra myndighedens side er blevet vedlagt et høringsskema i excel ark, hvortil der så lægges op til, at høringssvaret følger et fast format.
* Det virker umiddelbart som om, at det er på det sundshedsfaglige område, at man har lavet de her svarskemaer.

