# Market Adaptation

Read [the entrypoint](../SKILL.md). Use this before writing any episode for a
new market, then record the answers in the series bible.

## Questions to answer per market

| Topic | Decide |
| --- | --- |
| Language and register | Dialogue language, regional variety, formal versus casual address, code-switching habits |
| Names and address | Common given names by age and class, honorifics, family terms, how strangers are addressed |
| Class and status markers | Housing, vehicles, uniforms, jewelry, workplace hierarchy that read instantly |
| Settings | Typical home, office, street and family-gathering layouts, light and climate |
| Wardrobe | Everyday and formal clothes, regional dress, always-worn items |
| Food and rituals | Meals, gifts, weddings, funerals, festivals that stage a confrontation naturally |
| Proof objects | Local documents, heirlooms and keepsakes shown without legible text |
| Taboos and sensitivities | Religion, politics, caste, ethnic stereotypes, authority figures, depictions of violence |
| Platform fit | Common episode length, subtitle expectation, vertical platform norms |

## Process

1. Write the answers as a short market card in the series bible.
2. Keep the card to facts you are confident of; mark the rest "verify with a
   native speaker" and surface those questions to the user.
3. Prefer specific local details over generic "exotic" markers.
4. Avoid stereotypes: give every character a want and a secret beyond their
   class or ethnicity.

## Language support check

The video model supports a fixed set of natively spoken dialogue languages.
Check the current list with `seedance-prompt-25-dialogue` before locking
dialogue in an unlisted language; such scenes may need audio-first production
or a different spoken language with subtitles.

## When the market deserves a pack

If a market will see repeated production, create a market pack: a story writer
with local formulas, honorifics and visual signifiers, and optionally a
dialogue partner with pronunciation lessons. See
`docs/ADD_A_MARKET.md` in the repository for the template. The Filipino pack
(`filipino-micro-drama`, `seedance-prompt-25-filipino`) is the reference
example.
