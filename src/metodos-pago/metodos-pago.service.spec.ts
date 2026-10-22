import { Test, TestingModule } from '@nestjs/testing';
import { MetodosPagoService } from './metodos-pago.service';
import { getRepositoryToken } from '@nestjs/typeorm';
import { MetodoPago } from './entities/metodo-pago.entity';

describe('MetodosPagoService', () => {
  let service: MetodosPagoService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        MetodosPagoService,
        {
          provide: getRepositoryToken(MetodoPago),
          useValue: {}, // Mock del repositorio
        },
      ],
    }).compile();

    service = module.get<MetodosPagoService>(MetodosPagoService);
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });
});
