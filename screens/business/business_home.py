from kivymd.uix.screen import MDScreen
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.button import MDFlatButton
from kivy.animation import Animation
from kivymd.uix.snackbar import Snackbar
from kivy.metrics import dp
from bigchaindb_driver import BigchainDB
from bigchaindb_driver.crypto import generate_keypair
from bigchaindb_driver.common.crypto import PrivateKey
import requests
from datetime import datetime
from  kivymd.uix.card import MDCardSwipe
from screens.escrow import Escrow
from multiprocessing import Process


class TransferPrompt(MDBoxLayout):
	pass

class CarItem(MDCardSwipe):
	make = StringProperty()
	model = StringProperty()
	screen = ''
	scrollview = None
	dialog = None
	

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.elevation = 3
	
	def transfer_dialog(self, fulfilled_creation_tx_car, current_email, home, *args):
		
		#Show a transfer pop dialog
		if not self.dialog:
			self.dialog = MDDialog(
                title="Transfer Vehicle",
                type="custom",
                content_cls=TransferPrompt(),
                buttons=[
                    MDFlatButton(
                        text="CANCEL",
                        on_press = self.close_carlog
                    ),
                    MDFlatButton(
                        text="SUBMIT",
                        on_press = lambda *args: self.transfer(fulfilled_creation_tx_car, current_email, home, *args)
                    ),
                ],
            )
		self.dialog.open()
		
	def close_carlog(self, obj):
		self.dialog.content_cls.ids.transfer_alert.text = ''
		self.dialog.content_cls.ids.key.text = ''
		self.dialog.content_cls.ids.recipient.text = ''
		self.dialog.dismiss()

	def maintenance_screen(self, app):
		
		#Go to vehicle history
		car_VIN = self.ids.name.tertiary_text
		app.root.get_screen('car_maintenance').load(car_VIN, self.screen)
		self.scrollview.clear_widgets()
		app.root.current = 'car_maintenance'
		
	def remove_card(self):
		self.scrollview.remove_widget(self) #Remove vehicle card after transfer
		
	def transfer(self, fulfilled_creation, current_email, home, *args):
		sender_pvt = self.dialog.content_cls.ids.key.text
		email_str = self.dialog.content_cls.ids.recipient.text
		
		#Error check for empty fields
		if sender_pvt != '' and email_str != '':
			
			#Establish connection to BigChainDB
			bdb_root_url = 'https://test.ipdb.io'
			bdb = BigchainDB(bdb_root_url)
			
			URL = "https://1r6m03cirj.execute-api.us-west-2.amazonaws.com/test/users" #For GET request
			email_list = email_str.split() #Splt the recipent emails into list
			recipient_public = []
			recipient_names = []
			
			#Send GET request for every email
			for i in email_list:
				user = requests.get(url = URL, params = {'email': i})
				dest_data = user.json()
				
				#If account was found in the database
				if len(dest_data['Items']) != 0:
					recipient_pub = dest_data['Items'][0]["publicKey"]["S"]
					dest_name = dest_data['Items'][0]["name"]["S"]
					recipient_public.append(recipient_pub)
					recipient_names.append(dest_name)
				else:
					self.dialog.content_cls.ids.transfer_alert.text = 'Account ' + i + ' was not found'
			
			#If any recipients found in database
			if len(recipient_public) != 0:
				#Initialize variables
				recipient_public_tup = tuple(recipient_public)
				owner_public_keys = fulfilled_creation['outputs'][0]['public_keys']
				car_VIN = self.ids.name.tertiary_text
				
				#Start process to transfer vehicle
				Process(target = Escrow.verify, args=(Escrow, sender_pvt, owner_public_keys, recipient_public_tup, recipient_public, self, fulfilled_creation, recipient_names, car_VIN)).start()
				
				self.dialog.content_cls.ids.transfer_alert.text = ''
				self.dialog.dismiss()
			
			self.dialog.content_cls.ids.key.text = ''
			self.dialog.content_cls.ids.recipient.text = ''
		else:
			self.dialog.content_cls.ids.transfer_alert.text = 'Fill in all the fields'
			
class BusinessHomeScreen(MDScreen):

	make_prompt = StringProperty("Make")
	model_prompt = StringProperty("Model")
	year_prompt = StringProperty("Year")
	vin_prompt = StringProperty("VIN")
	mileage_prompt = StringProperty("Mileage")

	make = StringProperty()
	model = StringProperty()
	year = StringProperty()
	vin = StringProperty()
	mileage = StringProperty()

	submit = StringProperty("Submit button pressed")

	def __init__(self, **kwargs):
		super(BusinessHomeScreen, self).__init__(**kwargs)
		Clock.schedule_once(self.on_start)
		self.snackbar = None
		self._interval = 0
	
	def wait_interval_car_created(self, interval):
		self._interval += interval
		if self._interval > self.snackbar.duration + 0.5:
			anim = Animation(y=dp(10), d=.2)
			anim.start(self.ids.submit_icon_new_vehicle)
			Clock.unschedule(self.wait_interval_car_created)
			self._interval = 0
			self.snackbar = None

	def snackbar_show_car_created(self):
		if not self.snackbar:
			self.snackbar = Snackbar(text="Vehicle Created Successfully!")
			self.snackbar.open()
			anim = Animation(y=dp(72), d=.2)
			anim.bind(on_complete=lambda *args: Clock.schedule_interval(
                self.wait_interval_car_created, 0))
			anim.start(self.ids.submit_icon_new_vehicle)


	def onCreateVehicleClick(self):
		car_key = generate_keypair() #Generate new car keypair
		
		#Establish connection to BigChainDB
		bdb_root_url = 'https://test.ipdb.io'
		bdb = BigchainDB(bdb_root_url)
		
		#Add timestamp
		dateTimeObj = datetime.now()
		localtime = dateTimeObj.strftime("%b/%d/%Y %I:%M:%S %p")
		
		make = self.ids.create_car_make.text
		model = self.ids.create_car_model.text
		year = self.ids.create_car_year.text
		vin = self.ids.create_car_vin.text
		mileage = self.ids.create_car_mileage.text
		
		#Error check for empty fields
		if make != '' and model != '' and year != '' and vin != '' and mileage != '':
			email = self.ids.email.text
			
			URL = "https://1r6m03cirj.execute-api.us-west-2.amazonaws.com/test/users"
			vin_check = bdb.assets.get(search = vin) #query for existing VIN in BigchainDB
			
			#If vin doesn't exist
			if len(vin_check) == 0:
				self.ids.creation_alert.text = ''
				self.ids.create_car_make.text = ''
				self.ids.create_car_model.text = ''
				self.ids.create_car_year.text = ''
				self.ids.create_car_vin.text = ''
				self.ids.create_car_mileage.text = ''
				
				#Send GET request to database
				user = requests.get(url = URL, params = {'email': email})
				data = user.json()
				recipient_pub = data['Items'][0]["publicKey"]["S"]
				recipient_names = []
				recipient_names.append(self.ids.account_name.title)
				
				#Create vehicle
				vehicle_asset = {
					'data': {
						'vehicle': {
							'make': make,
							'VIN': vin,
							'model': model,
							'year': year,
							'mileage': mileage,
						}
					}
				}

				self.snackbar_show_car_created()
				
				#Prepare the creation of car
				prepared_creation_tx_car = bdb.transactions.prepare(
					operation='CREATE',
					signers=car_key.public_key,
					recipients=(recipient_pub),
					asset=vehicle_asset,
					metadata= {'owner_key': recipient_pub, 'owner_name': recipient_names}
				)
				
				#fulfill the creation of the car by signing with the car's private key
				fulfilled_creation_tx_car = bdb.transactions.fulfill(
					prepared_creation_tx_car,
					private_keys=car_key.private_key
				)
				
				#send the creation of the car to bigchaindb
				sent_creation_tx_car = bdb.transactions.send_commit(fulfilled_creation_tx_car)
				
				self.add_card(vehicle_asset, fulfilled_creation_tx_car)

				maint_data = 'Vehicle Created'
	
				#Prepare the creation of log
				prepared_creation_tx_maintenance = bdb.transactions.prepare(
					operation='CREATE',
					signers=car_key.public_key,
					recipients=(car_key.public_key),
					metadata= {'maintenance': maint_data, 'date': localtime, 'vin': vin, 'type': 'transfer', 'mileage': mileage, 'owner': recipient_names}
				)
				
				#fulfill the creation of the log
				fulfilled_creation_tx_maintenance = bdb.transactions.fulfill(
					prepared_creation_tx_maintenance,
					private_keys=car_key.private_key
				)
				
				#send the creation of the log to BigchainDB
				sent_creation_tx_maintenance = bdb.transactions.send_commit(fulfilled_creation_tx_maintenance)
			else:
				self.ids.creation_alert.text = 'VIN already exists'
				self.ids.create_car_vin.text = ''
		else:
			self.ids.creation_alert.text = 'Fill in all the fields'
    
	def add_card(self, vehicle, fulfilled_creation_tx_car):
		card = CarItem();
		
		#Set card data
		card.screen = self.name
		card.scrollview = self.ids.content
		card.ids.name.text = vehicle['data']['vehicle']['make']
		card.ids.name.secondary_text = vehicle['data']['vehicle']['model']
		card.ids.name.tertiary_text = vehicle['data']['vehicle']['VIN']
		card.ids.transfer.on_press=lambda *args: card.transfer_dialog(fulfilled_creation_tx_car, self.ids.email.text, self.ids.content, *args)
		
		self.ids.content.add_widget(card) #Add card to scrollview
    
	def load(self):
		already_in = []
		
    		#Establish connection to BigChainDB
		bdb_root_url = 'https://test.ipdb.io'
		bdb = BigchainDB(bdb_root_url)
		
		#Send GET request to database
		email = self.ids.email.text
		URL = "https://1r6m03cirj.execute-api.us-west-2.amazonaws.com/test/users"
		user = requests.get(url = URL, params = {'email': email})
		data = user.json()
		self.ids.account_name.title = data['Items'][0]['name']['S']
		pub = data['Items'][0]['publicKey']["S"]
		
		data_list = bdb.metadata.get(search = pub) #Query BigchainDB for public key of user in metadata
		
		#Load all vehicles which have the public key in metadata
		for i in data_list:
			temp = bdb.transactions.get(asset_id=i['id'])

			if pub in temp[-1]['metadata']['owner_key']:
				if temp[-1]['operation'] == 'CREATE':
					vehicle = temp[-1]['asset']
					self.add_card(vehicle, temp[-1])
				elif temp[-1]['operation'] == 'TRANSFER' and (temp[-1]['asset']['id'] not in already_in):
					check = bdb.transactions.get(asset_id=temp[-1]['asset']['id'])
					if(pub in check[-1]['metadata']['owner_key']):
						already_in.append(check[-1]['asset']['id'])
						vehicle = check[0]['asset']
						self.add_card(vehicle, temp[-1])
	
	def on_start(self, *args):
		pass

	def wait_interval_form_submitted(self, interval):
		self._interval += interval
		if self._interval > self.snackbar.duration + 0.5:
			anim = Animation(y=dp(10), d=.2)
			anim.start(self.ids.submit_form)
			Clock.unschedule(self.wait_interval_form_submitted)
			self._interval = 0
			self.snackbar = None

	def snackbar_show_form_submitted(self):
		if not self.snackbar:
			self.snackbar = Snackbar(text="Maintenance Submitted Successfully!")
			self.snackbar.open()
			anim = Animation(y=dp(72), d=.2)
			anim.bind(on_complete=lambda *args: Clock.schedule_interval(
                self.wait_interval_form_submitted, 0))
			anim.start(self.ids.submit_form)

	def clock_next(self, app):
		Clock.schedule_once(self.next)
		
	def logout(self, root, app):
		self.ids.content.clear_widgets()
		app.root.current = 'startup_screen'
    	
	def next(self):
		#Go to the next page
		self.ids.form.load_next(mode="next")
		self.ids.maint_label.text_color=(76/255, 175/255, 80/255, 1)
		self.ids.progress_zero.value = 100
		self.ids.maint_icon.text_color = (76/255, 175/255, 80/255, 1)

	def previous(self):
		#Go to previous page
		self.ids.form.load_previous()
		self.ids.maint_label.text_color=(1, 1, 1, 1)
		self.ids.progress_zero.value = 50
		self.ids.maint_icon.text_color = (1, 1, 1, 1)
	
	def submit(self):
		
		#Establish connection to BigChainDB
		bdb_root_url = 'https://test.ipdb.io'
		bdb = BigchainDB(bdb_root_url)
		
		#Get date and time for maintenance creation
		dateTimeObj = datetime.now()
		localtime = dateTimeObj.strftime("%b/%d/%Y %I:%M:%S %p")
		
		#Initialize variables
		customer_vin = self.ids.vin.text
		customer_mileage = self.ids.mileage.text
		maint_data = self.ids.maint_performed.text
		pvt = self.ids.user_key.text
		
		#Error check for empty fields
		if pvt != '' and customer_vin != '' and maint_data != '' and customer_mileage != '':
			temp = bdb.assets.get(search = customer_vin) #Query BigchainDB for vehicle VIN
			
			URL = "https://1r6m03cirj.execute-api.us-west-2.amazonaws.com/test/users"
			
			#Send GET request to database
			email = self.ids.email.text
			company = self.ids.account_name.title
			user = requests.get(url = URL, params = {'email': email})
			data = user.json()
			
			pub = data['Items'][0]['publicKey']["S"]
			
			#Check if inputted private key is valid
			try:
				encrypt_pvt = PrivateKey(pvt)
				decrypted_pub = encrypt_pvt.get_verifying_key().encode().decode()
				if decrypted_pub == pub:
					valid_key = True
				else:
					valid_key = False
			except:
				valid_key = False
			
			#If all inputted information is correct
			if len(temp) != 0 and valid_key:
				temp = temp[0]
				info = bdb.transactions.get(asset_id = temp['id'])
				car_key = info[0]['inputs'][0]['owners_before'][0]
				owners = info[-1]['metadata']['owner_name']
				self.snackbar_show_form_submitted()
				
				#Prepare the creation of the maintenance owned by the mechanic
				prepared_creation_tx_maintenance = bdb.transactions.prepare(
					operation='CREATE',
					signers=pub,
					metadata= {'maintenance': maint_data, 'date': localtime, 'vin': customer_vin, 'type': 'maint', 'company': company, 'mileage': customer_mileage, 'owner': owners}
				)
				
				#fulfill the creation of the maintenance owned by the mechanic
				fulfilled_creation_tx_maintenance = bdb.transactions.fulfill(
					prepared_creation_tx_maintenance,
					private_keys=pvt
				)
				
				#send the creation of the maintenance to bigchaindb
				sent_creation_tx_maintenance = bdb.transactions.send_commit(fulfilled_creation_tx_maintenance)
				
				#Prepare proper transaction input to transfer maintenance to car
				creation_tx_maintenance = fulfilled_creation_tx_maintenance
				
				asset_id_maintenance = creation_tx_maintenance['id']
				
				transfer_asset_maintenance = {
					'id': asset_id_maintenance,
				}
				
				output_index = 0
				output = creation_tx_maintenance['outputs'][output_index]
				
				transfer_input_maintenance = {
					'fulfillment': output['condition']['details'],
					'fulfills': {
						'output_index': output_index,
						'transaction_id': creation_tx_maintenance['id']
					},
					'owners_before': output['public_keys']
				}
				
				#prepare the transfer of maintenance to car
				prepared_transfer_tx_maintenance = bdb.transactions.prepare(
					operation='TRANSFER',
					asset=transfer_asset_maintenance,
					inputs=transfer_input_maintenance,
					recipients=car_key,
				)
				
				#fulfill the transfer of maintenance to car
				fulfilled_transfer_tx_maintenance = bdb.transactions.fulfill(
					prepared_transfer_tx_maintenance,
					private_keys=pvt,
				)
				
				#send the transfer of the maintenance to bigchaindb
				sent_transfer_tx_maintenance = bdb.transactions.send_commit(fulfilled_transfer_tx_maintenance)

				self.ids.maint_alert.text = ''
				self.ids.vin.text = ''
				self.ids.maint_performed.text = ''
				self.ids.mileage.text = ''
				self.ids.user_key.text = ''
			else:
				self.ids.maint_alert.text = 'Incorrect Vin or Private Key'
				self.ids.vin.text = ''
				self.ids.user_key.text = ''
		else:
			self.ids.maint_alert.text = 'Fill in all the fields'
