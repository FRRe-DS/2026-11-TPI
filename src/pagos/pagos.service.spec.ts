import { Test, TestingModule } from '@nestjs/testing';
import { PagosService } from './pagos.service';
import { getRepositoryToken } from '@nestjs/typeorm';
import { Pago } from './entities/pago.entity';

describe('PagosService', () => {
  let service: PagosService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PagosService,
        {
          provide: getRepositoryToken(Pago),
          useValue: {}, // Mock del repositorio
        },
      ],
    }).compile();

    service = module.get<PagosService>(PagosService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });
});
