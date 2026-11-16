// Runs Fulldex's own Identify + Prepare (gba/frontend/games.h of the PR branch) on ROM files.
#include "games.h"
#include <cstdio>
using namespace gbaw::Games;
int main(int argc, char** argv)
{
    for (int i = 1; i + 1 < argc; i += 2)
    {
        Game g;
        g.rom = argv[i];
        g.fileName = g.rom.substr(g.rom.find_last_of('/') + 1);
        std::vector<uint8_t> rom;
        if (!ReadFile(g.rom, rom)) { printf("%s: can't read\n", argv[i]); continue; }
        Identify(g, rom);
        std::vector<uint8_t> out; std::string err;
        const bool ok = Prepare(g, out, err);
        printf("%-48s patch=%-12s forced=%d known=%d why=\"%s\" prepare=%s\n", g.fileName.c_str(),
               g.patch.empty() ? "(none)" : g.patch.c_str(), (int)g.forced, (int)g.known, g.why.c_str(), ok ? "ok" : err.c_str());
        if (ok) { FILE* f = fopen(argv[i + 1], "wb"); fwrite(out.data(), 1, out.size(), f); fclose(f); }
    }
}
