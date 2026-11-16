// Gen 3 Evolved widescreen v2: weather sprites (pokeemerald-expansion 1.16.3 field_weather_effect.c)
// widened for Fulldex's wide picture.
//
// Fog (horizontal and diagonal), volcanic ash and sandstorm each tile the screen with 5 columns
// of 64-pixel sprites that wrap at x = 272. That guarantees only 256 pixels of cover, and a
// 16:9 picture needs 284. Each gets a 6th column: the sprite callback is replaced so the
// columns wrap with a 384-pixel period at x = 312 (always covering -40..280), and each
// column-0 sprite creates one extra sprite for column 5 from its own template. The extra
// follows its parent's y and destroys itself as soon as the parent is gone, so the original
// create and destroy code (and the weather's sprite arrays) are untouched.
//
// Rain: drops landed on 30 tile columns (x 0..232) and were drawn only for -8 <= x <= 248.
// They now land on 36 columns (x -24..256). The drawing limits are widened by an
// instruction patch in g3e_widescreen_v2.py.

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef signed short s16;
typedef unsigned int u32;
typedef signed int s32;

struct Sprite
{
    u8 oam[8];
    const void *anims;
    const void *images;
    const void *affineAnims;
    const void *template;
    const void *subspriteTables;
    void (*callback)(struct Sprite *);
    s16 x, y;
    s16 x2, y2;
    s8 centerToCornerVecX, centerToCornerVecY;
    u8 animNum, animCmdIndex;
    u8 animDelayCounter, affineAnimDelayCounter;
    s16 data[8];
    u8 flags3E;              // bit 0 inUse, bit 1 coordOffsetEnabled, bit 2 invisible
    u8 flags3F;
    u16 sheetTileStart;
    u8 subspriteTableNum;
    u8 subpriority;
};
_Static_assert(sizeof(struct Sprite) == 0x44, "struct Sprite size");

#define MAX_SPRITES 80        // this build's sprite count (CreateSprite loops to 80)

extern struct Sprite gSprites[];
extern s16 gSpriteCoordOffsetX;
extern s16 gSpriteCoordOffsetY;
extern u8 *const gWeatherPtr;               // const pointer in ROM to the RAM struct Weather
extern const u16 G3E_RainFallingDurations[];  // [isDownpour][2]
extern const s16 G3E_RainMovement[];          // [isDownpour][2] (dx, dy)

u8 G3E_CreateSprite(const void *template, s16 x, s16 y, u8 subpriority);
void G3E_DestroySprite(struct Sprite *sprite);
void G3E_StartSpriteAnim(struct Sprite *sprite, u8 animNum);

// The original callbacks: every weather sprite's callback field still points at these (the
// templates do); their code now jumps here.
void G3E_FogHorizontalSpriteCallback(struct Sprite *);
void G3E_UpdateAshSprite(struct Sprite *);
void G3E_UpdateFogDiagonalSprite(struct Sprite *);
void G3E_UpdateSandstormSprite(struct Sprite *);

// struct Weather offsets in this build (read from the original callbacks)
#define W_FOGH_SCROLL_POS_X   0x22E
#define W_ASH_BASE_X          0x23C
#define W_SANDSTORM_BASE_X    0x24E
#define W_SANDSTORM_POS_Y     0x250
#define W_FOGD_BASE_X         0x258
#define W_FOGD_POS_Y          0x25A
#define W_IS_DOWNPOUR         0x21C

#define WEATHER_U16(off) (*(u16 *)(gWeatherPtr + (off)))
#define WEATHER_U8(off)  (*(u8 *)(gWeatherPtr + (off)))

enum { KIND_FOGH, KIND_ASH, KIND_FOGD, KIND_SAND, KIND_COUNT };

static const u16 sBaseOffset[KIND_COUNT] = { W_FOGH_SCROLL_POS_X, W_ASH_BASE_X, W_FOGD_BASE_X, W_SANDSTORM_BASE_X };

static void (*const sParentCallback[KIND_COUNT])(struct Sprite *) = {
    G3E_FogHorizontalSpriteCallback, G3E_UpdateAshSprite, G3E_UpdateFogDiagonalSprite, G3E_UpdateSandstormSprite,
};

#define COLUMNS       6
#define WRAP_AT       312                 // centres in [WRAP_AT - 384, WRAP_AT): cover -40..280
#define EXTRA_LINK    7                   // parent: data[7] = extra sprite id + 1
                                          // extra: data[7] = parent id, data[6] = kind

static s16 ColumnX(u32 base, s32 column)
{
    s32 x = (s32)base + 32 + column * 64;
    if (x >= WRAP_AT)
        x -= COLUMNS * 64;
    return x & 0x1FF;
}

void Wide_WeatherExtraCallback(struct Sprite *extra);

static void EnsureExtraColumn(struct Sprite *parent, s32 column, u32 kind)
{
    if (column != 0)
        return;
    s32 link = parent->data[EXTRA_LINK];
    if (link > 0 && link <= MAX_SPRITES)
    {
        struct Sprite *e = &gSprites[link - 1];
        if ((e->flags3E & 1) && e->callback == Wide_WeatherExtraCallback && e->data[EXTRA_LINK] == parent - gSprites)
            return;
    }
    u8 id = G3E_CreateSprite(parent->template, 0, parent->y, parent->subpriority);
    if (id >= MAX_SPRITES)
    {
        parent->data[EXTRA_LINK] = 0;
        return;
    }
    struct Sprite *e = &gSprites[id];
    e->callback = Wide_WeatherExtraCallback;
    e->data[EXTRA_LINK] = parent - gSprites;
    e->data[6] = kind;
    e->y = parent->y;
    e->y2 = parent->y2;
    e->x = ColumnX(WEATHER_U16(sBaseOffset[kind]), COLUMNS - 1);
    parent->data[EXTRA_LINK] = id + 1;
}

void Wide_WeatherExtraCallback(struct Sprite *extra)
{
    u32 kind = (u16)extra->data[6];
    struct Sprite *parent = &gSprites[extra->data[EXTRA_LINK]];
    if (kind >= KIND_COUNT || !(parent->flags3E & 1) || parent->callback != sParentCallback[kind])
    {
        G3E_DestroySprite(extra);
        return;
    }
    extra->y = parent->y;
    extra->y2 = parent->y2;
    extra->x = ColumnX(WEATHER_U16(sBaseOffset[kind]), COLUMNS - 1);
}

// FogHorizontalSpriteCallback: column = data[0]
void Wide_FogHorizontalSpriteCallback(struct Sprite *sprite)
{
    sprite->y2 = (u8)gSpriteCoordOffsetY;
    sprite->x = ColumnX(WEATHER_U16(W_FOGH_SCROLL_POS_X), sprite->data[0]);
    EnsureExtraColumn(sprite, sprite->data[0], KIND_FOGH);
}

// UpdateAshSprite: tOffsetY = data[0], tCounterY = data[1], column = data[2]
void Wide_UpdateAshSprite(struct Sprite *sprite)
{
    if (++sprite->data[1] > 5)
    {
        sprite->data[1] = 0;
        sprite->data[0]++;
    }
    sprite->y = gSpriteCoordOffsetY + sprite->data[0];
    sprite->x = ColumnX(WEATHER_U16(W_ASH_BASE_X), sprite->data[2]);
    EnsureExtraColumn(sprite, sprite->data[2], KIND_ASH);
}

// UpdateFogDiagonalSprite: column = data[0]
void Wide_UpdateFogDiagonalSprite(struct Sprite *sprite)
{
    sprite->y2 = WEATHER_U16(W_FOGD_POS_Y);
    sprite->x = ColumnX(WEATHER_U16(W_FOGD_BASE_X), sprite->data[0]);
    EnsureExtraColumn(sprite, sprite->data[0], KIND_FOGD);
}

// UpdateSandstormSprite: column = data[0]
void Wide_UpdateSandstormSprite(struct Sprite *sprite)
{
    sprite->y2 = WEATHER_U16(W_SANDSTORM_POS_Y);
    sprite->x = ColumnX(WEATHER_U16(W_SANDSTORM_BASE_X), sprite->data[0]);
    EnsureExtraColumn(sprite, sprite->data[0], KIND_SAND);
}

static u32 UMod(u32 a, u32 b) { while (a >= b) a -= b; return a; }
static u32 UDiv(u32 a, u32 b) { u32 q = 0; while (a >= b) { a -= b; q++; } return q; }

// StartRainSpriteFall: tCounter = data[0], tRandom = data[1], tPosX = data[2], tPosY = data[3],
// tState = data[4]. As the original, except the landing column: 36 columns from x = -24.
void Wide_StartRainSpriteFall(struct Sprite *sprite)
{
    if (sprite->data[1] == 0)
        sprite->data[1] = 361;
    u32 rand = (u32)(s32)sprite->data[1] * 1103515245u + 12345u;   // ISO_RANDOMIZE2
    u32 r = UMod((rand & 0x7FFF0000) >> 16, 600);
    sprite->data[1] = r;

    u32 downpour = WEATHER_U8(W_IS_DOWNPOUR);
    u16 frames = G3E_RainFallingDurations[downpour * 2];
    s32 tileX = (s32)UMod(r, 36) - 3;
    s32 tileY = (s32)UDiv(r, 30);

    sprite->data[2] = (s16)((tileX << 7) - G3E_RainMovement[downpour * 2] * frames);
    sprite->data[3] = (s16)((tileY << 7) - G3E_RainMovement[downpour * 2 + 1] * frames);

    G3E_StartSpriteAnim(sprite, 0);
    sprite->data[4] = 0;
    sprite->flags3E &= ~2;     // coordOffsetEnabled = FALSE
    sprite->data[0] = frames;
}
