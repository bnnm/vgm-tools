# Wwise UAsset unpacking

Recent Unreal Engine 5 games using Wwise pack assets in `.uasset`+`ubulk`, but `.wem` IDs are
part of serialized class data. These may be extracted correctly by fmodel w/ `.usmap`, but
sometimes only `.uasset`+`ubulk` can be dumped.

Those `.wem` ID are needed by `wwiser` to generate `.txtp`, because the Wwise engine works like that.
In Unreal Engine the *Wwise plugin* knows how to read the serialized `.wem` ID, but when extracting
`.uassets`+`ubulk` as raw files it's hard to unpack these IDs.

In those cases (specially when *WwiseAssetLibrary* and similar names are used) we can use a
workaround to dump + rename files, since newer `.wem` have hash metadata referenced by `.bnk`.


## Extracting assets
- use Fmodel to extract *all* audio `.uasset`+`.ubulk` and similar files
  - usually in *Wwise* / *Sound* / *Audio* / *Events* folders, don't just extract a single "music.uasset"
  - include `InitBank.uasset` and similar files, which may be in another dir

- copy `uassets-wwise-dumper.py`, `uassets-wwise-renamer.py`, and `wwiser.pyz` to the extracted folder
  - `.uasset`+`.ubulk` may be in subdirs

- run `uassets-wwise-dumper.py` to unpack `.wem`/`.bnk`
  - this creates a `_out/Wwise` dir with everything, but has incorrect names

- run *wwiser* and dump `banks.xml` from ALL extracted `.bnk` (needed to rename files)
  - CLI: `wwiser.py *.bnk -r`
  - GUI: load root dir + *dump* banks

- run `uassets-wwise-renamer.py` (needs banks.xml) to rename all `.wem`/`.bnk`

  
If all went well, the `_out` dir should have renamed `.wem` and `.bnk`. The above process may create 2 folders:
- `_dupes`: will contain `.wem`/`.bnk` that are repeated, which is very common in UE5
- `_unknowns`: will contain `.wem` that aren't referenced by any `.bnk`.

Since this script can only rename `.wem` that are referenced by some `.bnk` (in `banks.xml`), any unused `.wem`
will be moved to `_unknowns`. It's possible to manually find the ID in `.uasset`, but since no `.bnk` use it
the ID itself isn't too useful (`wwiser` can't create `.txtp` for them). This can be seen for example in
`.uasset` containing `.wem` for planned DLC.

Conversely, `.uasset` and `.bnk` can also point to `.wem` that don't exist (either deleted, or future assets).
This doesn't affect renaming, but `.txtp` may not be playable as-is. This seems correct and just how the thing
is made.

Finally, use *wwiser* to make `.txtp` as needed from the renamed files.


## Issues
If you get crashes with `uassets-wwise-dumper.py`, try changing `IS_UE53`/`IS_UE54` flags in the script,
or report. UE changes `.uasset` format from time to time so things may break.

If Fmodel has issues unpacking some `.ubulk`, try retoc: https://github.com/trumank/retoc
- `retoc.exe -a (hex aes key) unpack pakchunk(name).utoc out`

Remember that it's VERY important you extract all sound-related `.uasset`+`.ubulk` to rename files.


## Reversing names
See *wwiser-tools/wstrings* repo, but reminder you can use `wstrings-ue-assets.py` to extract strings
from `.uassets` to `ww_(path).txt`

Then use `wwiser.py *.bnk -r -sl` to make a `wwnames-*.txt` name list, and use `words.py` with `wwnames*.txt`
 adn the `ww*.txt` (renamed to `ww.txt`) for quick reversing of many names.
