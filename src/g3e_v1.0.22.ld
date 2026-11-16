/* Generation 3 Evolved v1.0.22 (CRC32 98E1DF5A) addresses, found by g3e_widescreen.py / by hand. */
/* Functions are Thumb: bit 0 set. */
G3E_DrawMetatileAt                       = 0x0813E5ED;
G3E_DrawMetatile                         = 0x0813E501;
G3E_SetGpuReg                            = 0x08164061;
G3E_CameraMove                           = 0x0815A331;
G3E_UpdateObjectEventsForCameraUpdate    = 0x08133195;
G3E_RotatingGatePuzzleCameraUpdate       = 0x081FFC11;
G3E_SetBerryTreesSeen                    = 0x080EA141;
G3E_TryDespawnOWEsCrossingMapConnection  = 0x082470CD;
sFieldCameraOffset       = 0x030013A8;
sHorizontalCameraPan     = 0x030013B4;
sVerticalCameraPan       = 0x030013B6;
gFieldCamera             = 0x030025E4;
gTotalCameraPixelOffsetX = 0x030025FC;
gTotalCameraPixelOffsetY = 0x030025FE;
gSaveBlock1Ptr           = 0x030052E0;
gMapHeader_mapLayout     = 0x02001B88;
gBackupMapLayout         = 0x0300261C;

/* weather (field_weather_effect.c) and sprites (sprite.c) */
G3E_CreateSprite                 = 0x0821963D;
G3E_DestroySprite                = 0x08218549;
G3E_StartSpriteAnim              = 0x08218E31;
G3E_FogHorizontalSpriteCallback  = 0x08156D19;
G3E_UpdateAshSprite              = 0x08156D65;
G3E_UpdateFogDiagonalSprite      = 0x08156E51;
G3E_UpdateSandstormSprite        = 0x08156F01;
gSprites                 = 0x02037168;
gSpriteCoordOffsetX      = 0x02036C22;
gSpriteCoordOffsetY      = 0x02036C24;
gWeatherPtr              = 0x08602A74;
G3E_RainFallingDurations = 0x0860EFFC;
G3E_RainMovement         = 0x0860F004;

SECTIONS
{
    . = 0x09F00000;
    .text : { *(.text*) *(.rodata*) }
    /DISCARD/ : { *(.data*) *(.bss*) *(COMMON) *(.comment) *(.ARM.*) }
}
