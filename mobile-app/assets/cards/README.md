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

Nothing is bundled by default: issuer card art is their copyright, and this is
a demo, not a distribution.
