#pragma once

//--------------------------------------------------
// �C���N���[�h
//--------------------------------------------------
#include <stdio.h>

//--------------------------------------------------
// ADX�N���X
//--------------------------------------------------
class clADX{
public:
	clADX();
	~clADX();

	// �`�F�b�N
	static bool CheckFile(void *data);

	// �f�R�[�h
	bool Decode(const char *filename,const char *filenameWAV);
	bool Decode(FILE *fp,void *data,int size,unsigned int address);

private:
	struct stHeader{
		unsigned short signature;    // �V�O�l�`�� 0x8000
		unsigned short dataOffset;   // �f�[�^�I�t�Z�b�g(�w�b�_�T�C�Y)-4
		unsigned char r04;           // �o�[�W�����H 3
		unsigned char r05;           // �u���b�N�T�C�Y�H 18
		unsigned char r06;           // �H 4
		unsigned char channelCount;  // �`�����l����
		unsigned int samplingRate;   // �T���v�����O���[�g
		unsigned int sampleCount;    // ���v�T���v����
		unsigned char r10;
		unsigned char r11;
		unsigned char r12;
		unsigned char r13;
		unsigned int r14;
		unsigned short r18;
		unsigned short r1A;
		unsigned short r1C;
		unsigned short r1E;
	};
	struct stInfo{//channelCount��3�ȏ�̎���(channelCount-2)�񕪑���
		unsigned short r00;
		unsigned short r02;
	};
	struct stAINF{
		unsigned int ainf;// 'AINF'
		unsigned int r04;
		unsigned char r08[0x10];
		unsigned short r18;
		unsigned short r1A;
		unsigned short r1C;
		unsigned short r1E;
	};
	stHeader _header;
	int *_data;
	static void Decode(int *d,unsigned char *s);
};
