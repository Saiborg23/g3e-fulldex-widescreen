// Gen 3 Evolved widescreen v2: the overworld camera (pokeemerald-expansion 1.16.3 field_camera.c)
// redone for 64x32-tile BG maps, so Fulldex can show up to 32 metatiles across.
//
// The original keeps a 32x32-tile (16x16-metatile) ring buffer per BG layer: 16 columns,
// of which only 15 are kept current, and the scroll register wraps at 256 pixels. Here each
// BG1-3 map is 64x32 tiles (two screen blocks side by side, BG screen size 1). The ring holds
// 32 metatile columns, from EXTRA_LEFT metatiles left of the camera's origin
// (gSaveBlock1Ptr->pos) to 32 - EXTRA_LEFT - 1 right of it, and the horizontal scroll wraps
// at 512 pixels.
//
// sFieldCameraOffset.xTileOffset now counts modulo 64 instead of 32. Every reader and writer
// of sFieldCameraOffset is in field_camera.c (checked: all 14 literal-pool references are in
// 0x0813E888-0x0813F1B8), and this file replaces each one that touches xTileOffset.
//
// Built freestanding; every G3E address comes from the linker script (g3e_v1.0.22.ld).

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef signed short s16;
typedef unsigned int u32;
typedef signed int s32;

#define EXTRA_LEFT 8      // metatile columns kept left of pos.x (original: effectively 1)
#define RING_COLS 32      // metatile columns in the ring (64 tiles)
#define RING_ROWS 16      // metatile rows (32 tiles, unchanged)

struct FieldCameraOffset
{
    u8 xPixelOffset;
    u8 yPixelOffset;
    u8 xTileOffset;      // now 0..63 (original 0..31)
    u8 yTileOffset;      // 0..31
    u8 copyBGToVRAM;
};

struct CameraObject
{
    void (*callback)(struct CameraObject *);
    u32 spriteId;
    s32 movementSpeedX;
    s32 movementSpeedY;
    s32 x;
    s32 y;
};

struct Coords16 { s16 x, y; };   // SaveBlock1.pos, its first member

// G3E data (addresses in the linker script)
extern struct FieldCameraOffset sFieldCameraOffset;
extern s16 sHorizontalCameraPan;
extern s16 sVerticalCameraPan;
extern struct CameraObject gFieldCamera;
extern u16 gTotalCameraPixelOffsetX;
extern u16 gTotalCameraPixelOffsetY;
extern struct Coords16 *gSaveBlock1Ptr;
extern const void *gMapHeader_mapLayout;   // gMapHeader.mapLayout (its first member)
// The map grid in memory: the map plus a 7-metatile margin (MAP_OFFSET) holding the connected
// maps' edges. Past it, MapGridGetMetatileIdAt returns the border block, which the wide view
// can reach within ~2 metatiles of a side connection.
extern struct { s32 width; s32 height; const u16 *map; } gBackupMapLayout;

// G3E functions
void G3E_DrawMetatileAt(const void *mapLayout, u16 offset, int x, int y);
void G3E_DrawMetatile(s32 metatileLayerType, const u16 *tiles, u16 offset);
void G3E_SetGpuReg(u8 regOffset, u16 value);
void G3E_CameraMove(int deltaX, int deltaY);
void G3E_UpdateObjectEventsForCameraUpdate(s16 x, s16 y);
void G3E_RotatingGatePuzzleCameraUpdate(s16 deltaX, s16 deltaY);
void G3E_SetBerryTreesSeen(void);
void G3E_TryDespawnOWEsCrossingMapConnection(void);

#define METATILE_LAYER_TYPE_COVERED 1
#define REG_OFFSET_BG1HOFS 0x14
#define REG_OFFSET_BG1VOFS 0x16
#define REG_OFFSET_BG2HOFS 0x18
#define REG_OFFSET_BG2VOFS 0x1A
#define REG_OFFSET_BG3HOFS 0x1C
#define REG_OFFSET_BG3VOFS 0x1E

// Offset into a 64x32 text BG map (screen size 1: two 32x32 screen blocks, left then right).
// tx and ty are even (metatile corners), so DrawMetatile's +1/+0x20/+0x21 stay in one block.
static inline u16 TilemapOffset(u32 tx, u32 ty)
{
    tx &= 63;
    ty &= 31;
    return ((tx & 32) << 5) | (ty << 5) | (tx & 31);
}

static inline u16 OffsetFor(s32 col, s32 row)
{
    return TilemapOffset(sFieldCameraOffset.xTileOffset + col * 2, sFieldCameraOffset.yTileOffset + row * 2);
}

// Columns past the in-memory grid repeat its outermost column (the connected map's terrain
// carrying on) instead of showing border blocks. Drawing only; collision is untouched.
static inline s32 ClampToGrid(s32 x)
{
    if (x < 0)
        return 0;
    if (x >= gBackupMapLayout.width)
        return gBackupMapLayout.width - 1;
    return x;
}

static void DrawColumn(s32 col)
{
    const void *layout = gMapHeader_mapLayout;
    s32 x = ClampToGrid(gSaveBlock1Ptr->x + col), y = gSaveBlock1Ptr->y;
    for (s32 row = 0; row < RING_ROWS; row++)
        G3E_DrawMetatileAt(layout, OffsetFor(col, row), x, y + row);
}

static void DrawRow(s32 row)
{
    const void *layout = gMapHeader_mapLayout;
    s32 x = gSaveBlock1Ptr->x, y = gSaveBlock1Ptr->y + row;
    for (s32 col = -EXTRA_LEFT; col < RING_COLS - EXTRA_LEFT; col++)
        G3E_DrawMetatileAt(layout, OffsetFor(col, row), ClampToGrid(x + col), y);
}

// The horizontal scroll, 0..511. xPixelOffset (a u8, so modulo 256) moves 1-2 pixels a frame,
// xTileOffset by 2 when a step starts; between them they never differ by more than a metatile,
// so the u8 difference, read as signed, gives the full 9-bit position.
static u32 ScrollX(void)
{
    s32 tilePixels = sFieldCameraOffset.xTileOffset * 8;
    s32 behind = (s8)(u8)(sFieldCameraOffset.xPixelOffset - tilePixels);
    return (u32)(tilePixels + behind + sHorizontalCameraPan) & 0x1FF;
}

void Wide_FieldUpdateBgTilemapScroll(void)
{
    u32 x = ScrollX();
    u32 y = (u16)(sVerticalCameraPan + sFieldCameraOffset.yPixelOffset + 8);

    G3E_SetGpuReg(REG_OFFSET_BG1HOFS, x);
    G3E_SetGpuReg(REG_OFFSET_BG1VOFS, y);
    G3E_SetGpuReg(REG_OFFSET_BG2HOFS, x);
    G3E_SetGpuReg(REG_OFFSET_BG2VOFS, y);
    G3E_SetGpuReg(REG_OFFSET_BG3HOFS, x);
    G3E_SetGpuReg(REG_OFFSET_BG3VOFS, y);
}

void Wide_DrawWholeMapView(void)
{
    for (s32 row = 0; row < RING_ROWS; row++)
        DrawRow(row);
    sFieldCameraOffset.copyBGToVRAM = 1;
}

static s32 MapPosToBgTilemapOffset(s32 x, s32 y)
{
    s32 col = x - gSaveBlock1Ptr->x;
    s32 row = y - gSaveBlock1Ptr->y;
    if (col < -EXTRA_LEFT || col >= RING_COLS - EXTRA_LEFT || row < 0 || row >= RING_ROWS)
        return -1;
    return OffsetFor(col, row);
}

void Wide_CurrentMapDrawMetatileAt(int x, int y)
{
    s32 offset = MapPosToBgTilemapOffset(x, y);
    if (offset >= 0)
    {
        G3E_DrawMetatileAt(gMapHeader_mapLayout, offset, x, y);
        sFieldCameraOffset.copyBGToVRAM = 1;
    }
}

void Wide_DrawDoorMetatileAt(int x, int y, u16 *tiles)
{
    s32 offset = MapPosToBgTilemapOffset(x, y);
    if (offset >= 0)
    {
        G3E_DrawMetatile(METATILE_LAYER_TYPE_COVERED, tiles, offset);
        sFieldCameraOffset.copyBGToVRAM = 1;
    }
}

// Called after CameraMove has moved pos by (x/2, y/2) metatiles and the tile offsets have moved
// with it: draws the column or row that has just come into the ring. (The original names are
// swapped: its "West" slice is the one drawn when the camera moves east.)
void Wide_RedrawMapSlicesForCameraUpdate(struct FieldCameraOffset *cameraOffset, int x, int y)
{
    (void)cameraOffset;
    if (x > 0)
        DrawColumn(RING_COLS - EXTRA_LEFT - 1);
    if (x < 0)
        DrawColumn(-EXTRA_LEFT);
    if (y > 0)
        DrawRow(RING_ROWS - 2);   // as the original: row 14 (row 15 is the one the ring drops)
    if (y < 0)
        DrawRow(0);
    sFieldCameraOffset.copyBGToVRAM = 1;
}

static void AddCameraTileOffset(s32 xOffset, s32 yOffset)
{
    sFieldCameraOffset.xTileOffset = (sFieldCameraOffset.xTileOffset + xOffset) & 63;
    sFieldCameraOffset.yTileOffset = (sFieldCameraOffset.yTileOffset + yOffset) & 31;
}

static void AddCameraPixelOffset(s32 xOffset, s32 yOffset)
{
    sFieldCameraOffset.xPixelOffset += xOffset;
    sFieldCameraOffset.yPixelOffset += yOffset;
}

// The step logic below is the original's, bugs included (the y-branch that sets deltaX).
static void StepCamera(int *deltaXOut, int *deltaYOut, int *speedXOut, int *speedYOut)
{
    int deltaX = 0, deltaY = 0;
    int movementSpeedX, movementSpeedY, curMovementOffsetX, curMovementOffsetY;

    if (gFieldCamera.callback != 0)
        gFieldCamera.callback(&gFieldCamera);
    movementSpeedX = gFieldCamera.movementSpeedX;
    movementSpeedY = gFieldCamera.movementSpeedY;
    curMovementOffsetX = gFieldCamera.x;
    curMovementOffsetY = gFieldCamera.y;

    if (curMovementOffsetX == 0 && movementSpeedX != 0)
        deltaX = movementSpeedX > 0 ? 1 : -1;
    if (curMovementOffsetY == 0 && movementSpeedY != 0)
        deltaY = movementSpeedY > 0 ? 1 : -1;
    if (curMovementOffsetX != 0 && curMovementOffsetX == -movementSpeedX)
        deltaX = movementSpeedX > 0 ? 1 : -1;
    if (curMovementOffsetY != 0 && curMovementOffsetY == -movementSpeedY)
        deltaX = movementSpeedX > 0 ? 1 : -1;

    gFieldCamera.x += movementSpeedX;
    gFieldCamera.x %= 16;
    gFieldCamera.y += movementSpeedY;
    gFieldCamera.y %= 16;

    *deltaXOut = deltaX;
    *deltaYOut = deltaY;
    *speedXOut = movementSpeedX;
    *speedYOut = movementSpeedY;
}

void Wide_CameraUpdateNoObjectRefresh(void)
{
    int deltaX, deltaY, speedX, speedY;
    StepCamera(&deltaX, &deltaY, &speedX, &speedY);
    if (deltaX != 0 || deltaY != 0)
    {
        G3E_CameraMove(deltaX, deltaY);
        AddCameraTileOffset(deltaX * 2, deltaY * 2);
        Wide_RedrawMapSlicesForCameraUpdate(&sFieldCameraOffset, deltaX * 2, deltaY * 2);
    }
    AddCameraPixelOffset(speedX, speedY);
}

void Wide_CameraUpdate(void)
{
    int deltaX, deltaY, speedX, speedY;
    StepCamera(&deltaX, &deltaY, &speedX, &speedY);
    if (deltaX != 0 || deltaY != 0)
    {
        G3E_CameraMove(deltaX, deltaY);
        G3E_UpdateObjectEventsForCameraUpdate(deltaX, deltaY);
        G3E_RotatingGatePuzzleCameraUpdate(deltaX, deltaY);
        G3E_SetBerryTreesSeen();
        AddCameraTileOffset(deltaX * 2, deltaY * 2);
        Wide_RedrawMapSlicesForCameraUpdate(&sFieldCameraOffset, deltaX * 2, deltaY * 2);
        G3E_TryDespawnOWEsCrossingMapConnection();
    }
    AddCameraPixelOffset(speedX, speedY);
    gTotalCameraPixelOffsetX -= speedX;
    gTotalCameraPixelOffsetY -= speedY;
}
