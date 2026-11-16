// TEST-ONLY: opens G3E's compiled-out pokeemerald-expansion debug menu from the start menu's Option slot.
typedef unsigned char u8;
u8 G3E_StartMenuDebugCallback(void);   // removes the start menu windows, hides the menu
void G3E_Debug_ShowMainMenu(void);
u8 Test_StartMenuDebug(void)
{
    G3E_StartMenuDebugCallback();
    G3E_Debug_ShowMainMenu();
    return 1;
}
