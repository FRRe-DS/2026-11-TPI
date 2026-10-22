import { Test, TestingModule } from '@nestjs/testing';
import { MetodosPagoController } from './metodos-pago.controller';
import { MetodosPagoService } from './metodos-pago.service';

describe('MetodosPagoController', () => {
  let controller: MetodosPagoController;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
      {
        provide: MetodosPagoService,
        useValue: {}, // Mock del servicio
      },
    ],
      
      controllers: [MetodosPagoController],
    }).compile();

    controller = module.get<MetodosPagoController>(MetodosPagoController);
  });

  it('should be defined', () => {
    expect(controller).toBeDefined();
  });
});
