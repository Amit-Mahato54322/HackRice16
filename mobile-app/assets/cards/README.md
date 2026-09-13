# Card artwork

Drop card images here and register them in `src/components/card-art.ts`:

```ts
export const CARD_IMAGES: Record<string, ImageSourcePropType> = {
  "chase-sapphire-preferred": require("../../assets/cards/chase-sapphire-preferred.png"),
};
```

Name each file after its VectorMint card id — `GET /dashboard` returns that as
`vectormint_card_id`. A card with no image here falls back to its issuer's
palette, so nothing breaks if one is missing.

## Provenance

Each image is the issuer's own published card art, fetched from their public
product pages. Credit belongs to the issuers; this is a demo, not a
distribution.

| File | Source |
|---|---|
| `chase-sapphire-preferred.png` | `creditcards.chase.com/.../card-art/sapphire_preferred_card.png` |
| `chase-freedom-unlimited.png` | supplied as a 1500x1000 WebP composite; cropped to the card |
| `amex-blue-cash-preferred.png` | `icm.aexp-static.com/.../cardarts/blue-cash-preferred.png` |
| `capital-one-venture.png` | Capital One product page |
| `bofa-customized-cash.png` | Bank of America product page |

Chase's own published asset (`card-art/freedom_unlimited_card_alt.png`) has a
"NO ANNUAL FEE!" ribbon baked across the corner, and no unribboned version is
served — the plain `freedom_unlimited_card.png` 404s, and Freedom Flex ships
the same treatment. So `chase-freedom-unlimited.png` here was cropped out of a
supplied composite instead: card bounds found by detecting the flat backdrop,
then the rounded corners flood-filled to transparent so it matches the other
cutouts. Cropped at 722x455 (aspect 1.587, against the real card's 1.586) and
downscaled to 578x364.
