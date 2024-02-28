#pragma once

//--------------------------------------------------
// �C���N���[�h
//--------------------------------------------------
#include "clUTF.h"

//--------------------------------------------------
// CRID�N���X
//--------------------------------------------------
class clCRID{
public:
	clCRID(unsigned int ciphKey1=0x207DFFFF,unsigned int ciphKey2=0x00B8F21B);

	// ���[�h/�J��
	static bool CheckFile(void *data,unsigned int size);
	bool LoadFile(const char *filename);

	// ����/�}���`�v���N�T
	bool Demux(const char *filename,const char *directory, bool is_demux_video, bool is_demux_info, bool is_demux_audio, bool is_convert_adx, bool is_internal_names, int stream_id);
	bool Mux(const char *filename,const char *filenameMovie,const char *filenameAudio);

	// �擾
	unsigned int GetFileCount(void){return _utf.GetPageCount();}
	const char *GetFilename(unsigned int index){return _utf.GetElement(index,"filename")->GetValueString();}

    //extra
    void SetMaskAudioFromFile(FILE *mask);
    void SetEncrypted(bool encrypted);

private:
	struct stInfo{
		unsigned int signature;      // �V�O�l�`�� 'CRID'
		unsigned int dataSize;       // �f�[�^�T�C�Y
		unsigned char r08;           // �s��(0)
		unsigned char dataOffset;    // �f�[�^�I�t�Z�b�g
		unsigned short paddingSize;  // �p�f�B���O�T�C�Y
		unsigned char chno;          // �s��(0)
		unsigned char r0D;           // �s��(0)
		unsigned char r0E;           // �s��(0)
		unsigned char dataType:2;    // �f�[�^�̎�� 0:Data 1:UTF(���^���) 2:Comment 3:UTF(�V�[�N���)
		unsigned char r0F_1:2;       // �s��(0)
		unsigned char r0F_2:4;       // �s��(0)
		unsigned int frameTime;      // �t���[������(0.01�b�P��)
		unsigned int frameRate;      // �t���[�����[�g(0.01fps�P��)
		unsigned int r18;            // �s��(0)
		unsigned int r1C;            // �s��(0)
	};
	clUTF _utf;
	unsigned char _videoMask1[0x20];
	unsigned char _videoMask2[0x20];
	unsigned char _audioMask[0x20];
	void InitMask(unsigned int key1,unsigned int key2);
	void MaskVideo(unsigned char *data,int size);
	void MaskAudio(unsigned char *data,int size);
	static void WriteInfo(FILE *fp,const char *string);

    //extra
    bool _encrypted;
};
