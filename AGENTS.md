# AGENTS.md

Modellnøytral arbeidsinstruks for kodeagenter i dette repoet. `CLAUDE.md` kan fortsatt brukes som historisk kontekst, men denne filen er den operative standarden.

## Formål

Repoet brukes som et orakel for spørsmål om:
- Nkom-dekning og bredbåndsutbygging
- ekomstatistikk, abonnement, inntekter og trafikk
- historiske tidsserier og fylkesvise sammenligninger

## Kilderekkefølge

Les i denne rekkefølgen når spørsmålet krever det:
1. `docs/EKOM.md` for `lib/ekom.parquet`
2. `docs/DEKNING.md` for historiske dekningsserier
3. `docs/DATA_DICT.md` for adresse-, mobil- og abonnementsfiler
4. `docs/TOOLS.md` for tilgjengelige API-er og builders
5. `historie.md` bare når spørsmålet gjelder tidlige år eller historisk kontekst

## Query Routing

Bruk minst mulig direkte SQL når et tryggere API finnes.

- Dekning 2024 per fylke: foretrekk `execute_malloy()`
- Dekning ellers: bruk `CoverageQuery` eller `execute_coverage()`
- Ekomstatistikk: bruk `EkomQuery` eller `execute_ekom()`
- Mobilabonnement per fylke fra `2025-Halvår`: bruk `execute_mobilabonnement_fylke()`
- Abonnementer fra `ab.parquet`: bruk `SubscriptionQuery`
- Historiske dekningstrender: bruk `HistoricalQuery` eller `HistoricalSpeedQuery`

## Chat-Kommandoer

I denne chatten skal slash-lignende kommandoer tolkes som operative kommandoer selv om chatfeltet ikke har native slash-støtte. Når brukeren skriver en av kommandoene under, skal agenten utføre handlingen direkte i repoet i stedet for å behandle teksten som et vanlig spørsmål.

- `/listhist`
  - Vis siste historiske spørringer i knowledge base.
- `/listhist <id>`
  - Hent og kjør historisk spørring med gitt id.
- `/graf`
  - Lag graf av siste resultat.
- `/tilxl`
  - Eksporter siste resultat til Excel.
- `/tilbilde`
  - Eksporter siste resultat til PNG-tabell.
- `/lagrehist`
  - Lagre siste verifiserte spørsmål og resultat til historikken.
  - Hvis siste spørsmål finnes i aktiv chatkontekst, bruk det som `question`.
  - Bygg eller gjenbruk kjørbar SQL som representerer resultatet som ble svart ut.
  - Lag en kort `result_summary` med de viktigste tallene.
  - Velg rimelig `category` basert på domenet, for eksempel `Dekning`, `Historikk`, `Ekom`, `Konkurranse` eller `Tilbydere`.
  - Lagre oppføringen direkte i knowledge base hvis brukeren eksplisitt ber om å lagre nå.
- `/lagrehist <spørsmål>`
  - Som over, men bruk teksten etter kommandoen som eksplisitt formulering av spørsmålet som skal lagres.

Ved bruk av `/lagrehist` skal agenten bekrefte hvilken historikk-id som ble opprettet.

## Svarstandard

- Oppgi alltid år eller rapportperiode eksplisitt.
- Oppgi definisjonen du har brukt når begrepet er tvetydig.
- Ikke gjett ved uklare spørsmål. Hvis det finnes mer enn én rimelig fortolkning, skal agenten stille oppfølgingsspørsmål før spørringen kjøres.
- Når tall er følsomme for definisjon, si kort hvilke filtre som ble brukt.
- Ved fylkesvise tabeller: sorter alfabetisk og legg `NASJONALT` nederst når relevant.
- Når brukeren ber om tabell eller når svaret naturlig er tabellform, skal agenten foretrekke en fastbredde ASCII-tabell i samme stil som `listhist`, ikke en vanlig markdown-tabell.
- Slike tabeller skal ha konsekvent kolonnebredde, høyrejusterte tall og være lette å lese direkte i chat og terminal.

## Obligatorisk Avklaring

Agenten skal be om presisering i stedet for å gjette når ett eller flere av disse punktene er uklare:

- År eller rapportperiode
  - Ikke default til `2024` eller annen periode bare fordi bruker ikke oppga år.
- Dekningstype
  - Hvis bruker spør om `dekning` uten å spesifisere teknologi eller hastighetsdefinisjon, spør hva som menes.
- Mobildekning
  - Hvis bruker skriver `mobil` eller `mobildekning`, spør om `4G`, `5G` eller begge.
- Høyhastighet
  - Hvis bruker skriver `høyhastighet` uten terskel, spør om eksakt hastighetsgrense.
- Ekom-metrikk
  - Hvis bruker spør om ekom uten å spesifisere `abonnement`, `inntekter` eller `trafikk`, spør om metrikk.
- Markedssegment
  - Hvis ekom-spørsmål om fast bredbånd ikke sier `privat`, `bedrift` eller `samlet`, spør om marked.
- Mobilabonnement
  - Hvis bruker spør om mobilabonnement uten å si `fakturert`, `kontantkort` eller `begge`, spør om dette.
- Tidsintervall
  - Hvis bruker spør over flere år eller sier `utvikling`, spør om de vil ha tidsserie per år/per rapport eller én enkelt periode.

Det er bedre å stille ett kort oppfølgingsspørsmål for mye enn å svare på feil tolkning.

## Domene-Regler

- `ekom.parquet`: bruk ikke `tp='Herav'` i totaler.
- Mobilabonnement per fylke finnes først fra `2025-Halvår` og bruker `tp='Herav'`.
- Fast bredbånd bedrift inkluderer både `Fast bredbånd` og `Datakommunikasjon` med mindre spørsmålet eksplisitt snevres inn.
- `ab.parquet` skal telles som rader. Ikke join mot `adr.parquet` for å telle abonnementer.
- Hastigheter i adresse- og mobilfiler er i `kbps`, ikke `Mbit/s`.
- For historiske fylkessammenligninger må fylkesreformen tas hensyn til.
- Når brukeren spør om hastighetsdekning som `gigabitdekning`, `100 Mbit-dekning`, `>=1000 Mbit` eller lignende uten å nevne teknologi, skal det tolkes som husstander med `ned >=` etterspurt hastighet uavhengig av teknologi.
- Hvis brukeren faktisk vil ha teknologispesifikk hastighetsdekning, må teknologien være eksplisitt nevnt, for eksempel `fiber med gigabit` eller `fiber + kabel med 100 Mbit`.

## Verifisering

- Kjør spørringen, les resultatet, og gjør en kort sanity check før du svarer.
- Hvis et API-kall gir tvilsomme nullverdier eller feil dimensjon, stopp og sjekk at riktig datakilde ble brukt.
- Foretrekk kodebaserte guardrails fremfor prompt-baserte huskeregler når du utvider repoet.
