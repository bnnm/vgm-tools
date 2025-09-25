# Demuxes .bik into audio-only files
#
# Shamelessly taken from VGMToolbox/format/VGMToolbox/format/BinkStream.cs
# Mostly C# > python conversion with minor tweaks (like demuxing newer bik videos).
# Results should be playable in binkplay.exe and vgmstream (possibly not all versions).


from enum import Enum
import argparse, glob, os, struct

USE_HEX_NAMES = True #False writes hex names like original vgmtoolbox
DEFAULT_SPLIT = False

class Constants:
    FileReadChunkSize = 71680 #0x11800 #snake magic, something about .NET's GC


class FileUtil:
    @staticmethod
    def AddHeaderToFile(headerBytes, sourceFile, destinationFile):
        readBuffer = bytearray(Constants.FileReadChunkSize)

        with open(destinationFile, "xb") as destinationStream:
            # write header
            destinationStream.write(headerBytes)

            # write the source file
            with open(sourceFile, "rb") as sourceStream:
                while True:
                    bytesRead = sourceStream.readinto(readBuffer)
                    if bytesRead == 0:
                        break
                    destinationStream.write(readBuffer[:bytesRead])


class DemuxOptionsStruct:
    def __init__(self):
        #self.ExtractVideo = False
        self.ExtractAudio = True
        #self.AddHeader = True
        self.SplitAudioStreams = False
        #self.AddPlaybackHacks = False
        self.RemoveVideoFlags = False

class BinkType(Enum):
    Version01 = 1
    Version02 = 2


class FrameOffsetStruct:
    def __init__(self):
        self.FrameOffset = 0
        self.IsKeyFrame = False


class ParseFile:
    @staticmethod
    def ParseSimpleOffset(stream, offset, length):
        stream.seek(offset)
        return stream.read(length)

    @staticmethod
    def CompareSegment(data, start, reference):
        return data[start:start+len(reference)] == reference

    @staticmethod
    def ReadByte(stream, offset):
        stream.seek(offset)
        return struct.unpack('<B', stream.read(1))[0]

    @staticmethod
    def ReadUintLE(stream, offset):
        stream.seek(offset)
        return struct.unpack('<I', stream.read(4))[0]


class ByteConversion:
    @staticmethod
    def GetLongValueFromString(splitAudioFileName):
        audioTrackIdString = splitAudioFileName.split(".")[0]
        hexString = audioTrackIdString.split("_")[-1]
        if USE_HEX_NAMES:
            return int(hexString, 10)
        else:
            return int(hexString, 16)

class BitConverter:
    @staticmethod
    def ToUInt32(valueBytes, startIndex):
        return struct.unpack('<I', valueBytes)[0]

    @staticmethod
    def GetBytes(value):
        return struct.pack('<I', value)

class BinkStream:
    BINK01_HEADER = bytes([0x42, 0x49, 0x4B])  # "BIK"
    BINK02_HEADER = bytes([0x4B, 0x42, 0x32])  # "KB2"

    DefaultFilePartAudioMulti = ".audio.multi"
    DefaultFilePartAudioSplit = ".audio.split"

    def __init__(self, filePath):
        self.FilePath = filePath
        self.FileExtensionAudio = BinkStream.DefaultFilePartAudioMulti


    def _getIndexForSplitAudioTrackFileName(self, splitAudioFileName):
        index = -1

        # get track ID
        audioTrackId = ByteConversion.GetLongValueFromString(splitAudioFileName)

        for i in range(len(self.audioTrackIds)):
            if self.audioTrackIds[i] == audioTrackId:
                index = i
                break

        return index

    def _writeChunkToStream(self, chunk, chunkId, streamWriters, fileExtension):
        if chunkId not in streamWriters:
            if USE_HEX_NAMES:
                name_format = "{}_{:02d}{}"
            else:
                name_format = "{}_{:08X}{}"

            destinationFile = os.path.join(
                os.path.dirname(self.FilePath),
                name_format.format(os.path.splitext(os.path.basename(self.FilePath))[0], chunkId, fileExtension)
            )

            streamWriters[chunkId] = open(destinationFile, "wb+")

        streamWriters[chunkId].write(chunk)

    def ParseHeader(self, inStream, offsetToHeader):
        fullHeaderSize = 0

        self.magicBytes = ParseFile.ParseSimpleOffset(inStream, offsetToHeader, 3)

        if ParseFile.CompareSegment(self.magicBytes, 0, BinkStream.BINK01_HEADER):
            self.binkVersion = BinkType.Version01

        elif ParseFile.CompareSegment(self.magicBytes, 0, BinkStream.BINK02_HEADER):
            versionId = ParseFile.ReadByte(inStream, offsetToHeader + 3)

            if versionId < 0x69:
                self.binkVersion = BinkType.Version01
            else:
                self.binkVersion = BinkType.Version02

        else:
            raise ValueError("Unrecognized Magic Bytes for Bink.")

        self.FrameCount = BitConverter.ToUInt32(ParseFile.ParseSimpleOffset(inStream, offsetToHeader + 8, 4), 0)
        self.VideoFlags = BitConverter.ToUInt32(ParseFile.ParseSimpleOffset(inStream, offsetToHeader + 0x24, 4), 0)
        self.AudioTrackCount = BitConverter.ToUInt32(ParseFile.ParseSimpleOffset(inStream, offsetToHeader + 0x28, 4), 0)

        self.audioTrackIds = [0] * self.AudioTrackCount

        # skip extra video sections
        baseOffset = offsetToHeader + 0x2C
        if self.VideoFlags & 0x000004:
            baseOffset += 6 * 0x02
        if self.VideoFlags & 0x010000:
            baseOffset += 12 * 0x02
        if self.binkVersion == BinkType.Version02:
            baseOffset += 4

        # skip max packet sizes and flags
        baseOffset += (self.AudioTrackCount * 0x04)
        baseOffset += (self.AudioTrackCount * 0x04)

        for i in range(self.AudioTrackCount):
            self.audioTrackIds[i] = BitConverter.ToUInt32(ParseFile.ParseSimpleOffset(inStream, baseOffset, 4), 0)
            baseOffset += 4

        self.FrameOffsetList = [FrameOffsetStruct() for _ in range(self.FrameCount)]

        # read offset table
        for i in range(self.FrameCount):
            frameOffset = ParseFile.ReadUintLE(inStream, baseOffset)
            baseOffset += 4

            isKeyFrame = (frameOffset & 1) == 1
            frameOffset &= 0xFFFFFFFE

            self.FrameOffsetList[i].FrameOffset = frameOffset
            self.FrameOffsetList[i].IsKeyFrame = isKeyFrame

        # last frame is file size
        baseOffset += 4

        fullHeaderSize = int(baseOffset)

        self.fullHeader = ParseFile.ParseSimpleOffset(inStream, offsetToHeader, fullHeaderSize)


    def _DoFinalTasks(self, streamWriters, demuxOptions):

        for key in streamWriters:
            try:
                streamWriter = streamWriters[key]

                if demuxOptions.ExtractAudio:
                    headerBytes = bytearray(self.fullHeader)

                    # set video size to minimum (real min is probably 4x4 but binkplay will accept this)
                    headerBytes[0x14:0x18] = BitConverter.GetBytes(1)
                    headerBytes[0x18:0x1C] = BitConverter.GetBytes(1)

                    headerOffset = 0x2c
                    removedSize = 0

                    # update video info
                    if self.binkVersion == BinkType.Version02:
                        headerOffset += 0x04 #can't be removed

                    if self.VideoFlags & 0x000004:
                        sectionSize = 6 * 0x02
                        if demuxOptions.RemoveVideoFlags:
                            headerBytes = headerBytes[0x00:headerOffset] + headerBytes[headerOffset + sectionSize:]
                            self.VideoFlags &= ~0x000004
                            removedSize += sectionSize
                        else:
                            headerOffset += sectionSize

                    if self.VideoFlags & 0x010000:
                        sectionSize = 12 * 0x02

                        if demuxOptions.RemoveVideoFlags:
                            headerBytes = headerBytes[0x00:headerOffset] + headerBytes[headerOffset + sectionSize:]
                            self.VideoFlags &= ~0x010000
                            removedSize += sectionSize
                        else:
                            headerOffset += sectionSize

                    if demuxOptions.RemoveVideoFlags:
                        headerBytes[0x24:0x28] = BitConverter.GetBytes(self.VideoFlags)


                    # update audio info
                    if demuxOptions.SplitAudioStreams:
                        audioTrackIndex = self._getIndexForSplitAudioTrackFileName(streamWriter.name)

                        # update audio info
                        headerBytes[0x28:0x2C] = BitConverter.GetBytes(1)

                        # copy 0x04 for max packet size + audio config + audio id (which doesn't need to be 0, binkc.exe/binkplay.exe allows any)
                        for _ in range(3):
                            readOffset = headerOffset + (audioTrackIndex * 4) #Nth track
                            copyOffset = headerOffset + (self.AudioTrackCount * 4) #after all audio
                            headerBytes[headerOffset:headerOffset+4] = headerBytes[readOffset:readOffset+4] #copy
                            headerBytes = headerBytes[0x00:headerOffset+4] + headerBytes[copyOffset:] #crunch

                            headerOffset += 0x04 #current header only has 1 track
                            removedSize += (self.AudioTrackCount - 1) * 4 #offsets must be adjusted
                    else:
                        audioTrackIndex = 0
                        headerOffset += (self.AudioTrackCount * 0xC)

                    # set file size
                    fileLength = streamWriter.tell() + len(headerBytes) - 8
                    headerBytes[0x04:0x08] = BitConverter.GetBytes(fileLength)


                    # insert frame offsets
                    previousFrameOffset = 0
                    frameOffset = 0
                    maxFrameSize = 0

                    frameStartLocation = headerOffset

                    for i in range(self.FrameCount):
                        # set previous offset
                        previousFrameOffset = frameOffset
                        frameOffset = self.NewFrameOffsetsAudio[audioTrackIndex][i]
                        frameOffset -= removedSize

                        if self.FrameOffsetList[i].IsKeyFrame:
                            # add key frame bit
                            frameOffsetBytes = BitConverter.GetBytes(frameOffset | 1)
                        else:
                            frameOffsetBytes = BitConverter.GetBytes(frameOffset)

                        # insert offset
                        headerBytes[frameStartLocation + (i * 4):frameStartLocation + (i * 4) + 4] = frameOffsetBytes

                        # calculate max frame size
                        if (frameOffset - previousFrameOffset) > maxFrameSize:
                            maxFrameSize = frameOffset - previousFrameOffset

                    # Add last frame offset (EOF)
                    fileLength = streamWriter.tell() + len(headerBytes)
                    headerBytes[frameStartLocation + (self.FrameCount * 4):frameStartLocation + (self.FrameCount * 4) + 4] = BitConverter.GetBytes(fileLength)

                    # insert max frame size
                    if (fileLength - frameOffset) > maxFrameSize:
                        maxFrameSize = fileLength - frameOffset

                    headerBytes[0x0C:0x10] = BitConverter.GetBytes(maxFrameSize)

                    # append to file
                    sourceFile = streamWriter.name
                    headeredFile = sourceFile + ".headered"

                    streamWriter.close()
                    FileUtil.AddHeaderToFile(headerBytes, sourceFile, headeredFile)
                    os.remove(sourceFile)
                    os.rename(headeredFile, sourceFile)

            except Exception as ex:
                name = streamWriters[key].name if streamWriters[key] else "UNKNOWN"
                raise Exception("Exception building header for file: {}{}{}".format(name, str(ex), os.linesep))

            finally:
                writer = streamWriters[key]
                if writer and not writer.closed:
                    writer.close()


    def DemultiplexStreams(self, demuxOptions):
        currentOffset = 0
        streamOutputWriters = {}

        _, fileExtension = os.path.splitext(self.FilePath)
        if demuxOptions.SplitAudioStreams:
            self.FileExtensionAudio = BinkStream.DefaultFilePartAudioSplit + fileExtension
        else:
            self.FileExtensionAudio = BinkStream.DefaultFilePartAudioMulti + fileExtension

        try:
            with open(self.FilePath, "rb") as fs:
                #fileSize = os.path.getsize(self.FilePath)
                currentOffset = 0

                # parse the header
                self.ParseHeader(fs, currentOffset)

                # setup audio frames
                self.NewFrameOffsetsAudio = [[] for _ in range(self.AudioTrackCount)]

                if demuxOptions.SplitAudioStreams:
                    for i in range(self.AudioTrackCount):
                        self.NewFrameOffsetsAudio[i] = [0] * self.FrameCount
                        self.NewFrameOffsetsAudio[i][0] = self.FrameOffsetList[0].FrameOffset
                elif self.AudioTrackCount > 0:
                    self.NewFrameOffsetsAudio[0] = [0] * self.FrameCount
                    self.NewFrameOffsetsAudio[0][0] = self.FrameOffsetList[0].FrameOffset

                #//////////////////////
                #// process each frame
                #//////////////////////
                for frameId in range(self.FrameCount):
                    try:
                        currentPacketOffset = 0

                        if demuxOptions.SplitAudioStreams:
                            #//////////////////
                            #// extract audio  - separate tracks
                            #//////////////////
                            for audioTrackId in range(self.AudioTrackCount):
                                audioPacketSize = BitConverter.ToUInt32(ParseFile.ParseSimpleOffset(fs, self.FrameOffsetList[frameId].FrameOffset + currentPacketOffset, 4), 0)
                                audioPacketSize += 4

                                if demuxOptions.ExtractAudio:
                                    audioPacket = ParseFile.ParseSimpleOffset(fs, self.FrameOffsetList[frameId].FrameOffset + currentPacketOffset, audioPacketSize)
                                    self._writeChunkToStream(audioPacket, self.audioTrackIds[audioTrackId], streamOutputWriters, self.FileExtensionAudio)

                                currentPacketOffset += audioPacketSize

                                # update audio frame id
                                if (frameId + 1) < self.FrameCount:
                                    self.NewFrameOffsetsAudio[audioTrackId][frameId + 1] = self.NewFrameOffsetsAudio[audioTrackId][frameId] + audioPacketSize
                        else:
                            #////////////////////////////////////
                            #// extract audio  - combine tracks
                            #////////////////////////////////////
                            for audioTrackId in range(self.AudioTrackCount):
                                audioPacketSize = BitConverter.ToUInt32(ParseFile.ParseSimpleOffset(fs, self.FrameOffsetList[frameId].FrameOffset + currentPacketOffset, 4), 0)
                                audioPacketSize += 4

                                if demuxOptions.ExtractAudio:
                                    audioPacket = ParseFile.ParseSimpleOffset(fs, self.FrameOffsetList[frameId].FrameOffset + currentPacketOffset, audioPacketSize)
                                    self._writeChunkToStream(audioPacket, 0, streamOutputWriters, self.FileExtensionAudio)

                                currentPacketOffset += audioPacketSize

                            # update audio frame id
                            if self.AudioTrackCount > 0 and (frameId + 1) < self.FrameCount:
                                self.NewFrameOffsetsAudio[0][frameId + 1] = self.NewFrameOffsetsAudio[0][frameId] + currentPacketOffset

                    except Exception as fex:
                        raise Exception("Exception processing frame 0x{:X} at offset 0x{:X}: {}".format(
                            frameId, self.FrameOffsetList[frameId].FrameOffset, str(fex)))

        except Exception as ex:
            raise Exception("Exception processing block at offset 0x{:X}: {}".format(currentOffset, str(ex)))

        finally:
            self._DoFinalTasks(streamOutputWriters, demuxOptions)

        return self.AudioTrackCount

def main():
    parser = argparse.ArgumentParser(description="Demultiplex Bink files into audio streams")
    parser.add_argument("files", nargs="*", help="Bink files to demux (default: *.bik)", default=['*.bik', '*.bk2'])
    parser.add_argument("-s", "--split", help="Split audio streams into separate files", action="store_true")
    parser.add_argument("-rvf", "--remove-video-flags", help="Removes some video-only chunks", action="store_true")

    args = parser.parse_args()
    if DEFAULT_SPLIT:
        args.split = True

    if not args.files:
        print("No .bik files found.")
        return

    files = []
    for file in args.files:
        if os.path.isfile(file):
            files += [file]
        else:
            files += glob.glob(file)

    for filepath in files:
        if any(item in filepath for item in [BinkStream.DefaultFilePartAudioMulti, BinkStream.DefaultFilePartAudioSplit]):
            continue

        print(f"Processing: {filepath}")
        bink = BinkStream(filepath)

        demuxOptions = DemuxOptionsStruct()
        demuxOptions.SplitAudioStreams = args.split
        demuxOptions.RemoveVideoFlags = args.remove_video_flags

        try:
            tracks = bink.DemultiplexStreams(demuxOptions)
            if tracks:
                print(f"Finished")
            else:
                print(f"File has no audio")
        except Exception as e:
            print(f"Error: {e}")
            raise

if __name__ == "__main__":
    main()
